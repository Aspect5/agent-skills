#!/usr/bin/env python3
"""Resolve the project's test command for bug-swarm, deterministically and portably.

Precedence (first hit wins):
  1. --test-cmd flag (caller override)
  2. $BUG_SWARM_TEST_CMD environment variable
  3. A test step parsed out of CI config (.github/workflows/*.yml, .gitlab-ci.yml,
     Makefile `test:` target, package.json "test" script) — comments are stripped
     first so a command is never lifted out of a `# ...` note.
  4. An ecosystem default inferred from manifest files present at the repo root
     (pytest / vitest|jest / go test / cargo test / mvn|gradle test / phpunit ...).
     A bare pyproject.toml is NOT treated as a pytest signal (it is commonly only
     packaging/bindings, e.g. maturin) — python defaults require a real pytest
     signal, and Cargo.toml / go.mod outrank an ambiguous pyproject.

The script NEVER guesses silently: it reports WHICH rule fired in the `source`
field, the detected `ecosystem`, and — when several stacks coexist — names them in
`note` so the caller can decide whether to trust it or ask the user. It self-roots
via `git rev-parse --show-toplevel` and supports --json. Exits non-zero only on a
hard failure (not a git repo, or no command resolvable AND --require set).

Dependency-light: Python 3 stdlib only. YAML/JSON parsing is intentionally shallow
and regex/`json`-based — we extract a likely test command, we do not validate CI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Resolution:
    test_cmd: str | None
    source: str  # which rule fired: flag|env|ci:<file>|ecosystem:<name>|none
    ecosystem: str | None  # detected stack, even when the command came from CI
    repo_root: str
    candidates: list[str]  # every command we considered, for transparency
    note: str | None = None


def fail(msg: str, *, as_json: bool) -> None:
    if as_json:
        sys.stdout.write(json.dumps({"ok": False, "error": msg}) + "\n")
    else:
        sys.stderr.write(f"error: {msg}\n")
    sys.exit(1)


def git_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return Path(out) if out else None


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# --- comment stripping (shallow, covers the common CI/Make/shell cases) ------


def _strip_inline_comment(line: str) -> str:
    """Drop a trailing `# ...` comment when the `#` is at line start or preceded
    by whitespace and not inside quotes. Shallow, but keeps us from lifting a
    command out of a comment line (the #1 false extraction)."""
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or line[i - 1].isspace():
                return line[:i]
    return line


def _strip_comments(text: str) -> str:
    return "\n".join(_strip_inline_comment(ln) for ln in text.splitlines())


# --- CI / config extraction --------------------------------------------------

_TEST_LINE = re.compile(
    r"\b("
    r"pytest|tox|nox|"
    r"(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test|"
    r"vitest|jest|mocha|ava|playwright\s+test|"
    r"go\s+test|"
    r"cargo\s+test|cargo\s+nextest\s+run|"
    r"mvn\s+(?:-\S+\s+)*test|gradle\s+(?:-\S+\s+)*test|\./gradlew\s+test|"
    r"phpunit|composer\s+(?:run\s+)?test|"
    r"rspec|rake\s+test|bundle\s+exec\s+(?:rspec|rake\s+test)|"
    r"dotnet\s+test|"
    r"ctest|make\s+(?:check|test)"
    r")\b[^\n#]*",
    re.IGNORECASE,
)


def _clean(cmd: str) -> str:
    # Strip YAML list markers, leading shell tokens, surrounding quotes/backticks.
    cmd = cmd.strip()
    cmd = re.sub(r"^-\s+", "", cmd)
    cmd = re.sub(r"^(run:|sh\s+-c\s+|bash\s+-c\s+)", "", cmd).strip()
    cmd = cmd.strip("`'\"").strip()
    return cmd


_CMD_KEY = re.compile(r"^(\s*)(?:-\s+)?(run|script|before_script|after_script):\s*(.*)$")


def _yaml_command_text(text: str) -> str:
    """Extract ONLY the shell commands from a CI YAML — the values of `run:`
    (GitHub Actions) and `script:`/`before_script:`/`after_script:` (GitLab),
    inline or block. This is what keeps us from matching a test word inside a
    `name:` label, a job id, or a comment (the #1 false extraction)."""
    lines = text.splitlines()
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        m = _CMD_KEY.match(lines[i])
        if not m:
            i += 1
            continue
        indent = len(m.group(1))
        rest = m.group(3).strip()
        i += 1
        if rest and rest[0] not in "|>[":
            out.append(rest)  # inline scalar: `run: cargo test -p foo`
            continue
        if rest.startswith("["):
            out.append(rest.strip("[]"))  # inline flow list: `script: [pytest]`
            continue
        # Block: gather lines indented deeper than the key (block scalar OR list).
        block_indent: int | None = None
        while i < n:
            ln = lines[i]
            if ln.strip() == "":
                i += 1
                continue
            cur = len(ln) - len(ln.lstrip())
            if cur <= indent:
                break
            if block_indent is None:
                block_indent = cur
            body = ln[block_indent:] if cur >= block_indent else ln.lstrip()
            body = re.sub(r"^-\s+", "", body)  # strip a YAML list marker
            out.append(body)
            i += 1
    return "\n".join(out)


def _first_test_cmd(command_text: str) -> str | None:
    """First whole command LINE that invokes a test runner. Returns the full
    line (preserving wrappers like `uv run ... pytest`), comments stripped."""
    for raw in command_text.splitlines():
        line = _strip_inline_comment(raw).strip()
        if line and _TEST_LINE.search(line):
            return _clean(line)
    return None


def from_github_workflows(root: Path, candidates: list[str]) -> tuple[str, str] | None:
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return None
    for wf in sorted(wf_dir.glob("*.y*ml")):
        cmd = _first_test_cmd(_yaml_command_text(read_text(wf)))
        if cmd:
            candidates.append(cmd)
            return cmd, f"ci:.github/workflows/{wf.name}"
    return None


def from_gitlab_ci(root: Path, candidates: list[str]) -> tuple[str, str] | None:
    gl = root / ".gitlab-ci.yml"
    if not gl.is_file():
        return None
    cmd = _first_test_cmd(_yaml_command_text(read_text(gl)))
    if cmd:
        candidates.append(cmd)
        return cmd, "ci:.gitlab-ci.yml"
    return None


def from_makefile(root: Path, candidates: list[str]) -> tuple[str, str] | None:
    for name in ("Makefile", "makefile", "GNUmakefile"):
        mk = root / name
        if not mk.is_file():
            continue
        text = read_text(mk)
        # Find a `test:` (or `check:`) target and confirm it has a real recipe
        # (a non-comment recipe line), then prefer the portable `make test`.
        target = re.search(
            r"^(?:test|check)\s*:.*$\n((?:\t.*\n?)+)", text, re.MULTILINE
        )
        if target:
            for line in target.group(1).splitlines():
                recipe = _strip_inline_comment(line.replace("\t", "", 1))
                recipe = re.sub(r"^@", "", recipe).strip()
                if recipe:
                    candidates.append("make test")
                    return "make test", f"ci:{name}"
    return None


def from_package_json(root: Path, candidates: list[str]) -> tuple[str, str] | None:
    pj = root / "package.json"
    if not pj.is_file():
        return None
    try:
        data = json.loads(read_text(pj) or "{}")
    except json.JSONDecodeError:
        return None
    scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
    if isinstance(scripts, dict) and isinstance(scripts.get("test"), str):
        raw = scripts["test"].strip()
        # Skip the npm-init placeholder.
        if raw and "no test specified" not in raw.lower():
            runner = _node_runner(root)
            cmd = f"{runner} test"
            candidates.append(cmd)
            return cmd, "ci:package.json"
    return None


# --- ecosystem defaults ------------------------------------------------------


def _node_runner(root: Path) -> str:
    if (root / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (root / "yarn.lock").is_file():
        return "yarn"
    if (root / "bun.lockb").is_file():
        return "bun"
    return "npm"


def _has_python_test_signal(root: Path) -> bool:
    """A *real* pytest signal — not a bare pyproject.toml, which is commonly just
    packaging or native bindings (maturin/setuptools) in a non-Python repo."""
    if (root / "pytest.ini").is_file() or (root / "tox.ini").is_file():
        return True
    setup_cfg = root / "setup.cfg"
    if setup_cfg.is_file() and "[tool:pytest]" in read_text(setup_cfg):
        return True
    pp = root / "pyproject.toml"
    if pp.is_file() and re.search(r"(?m)^\[tool\.pytest", read_text(pp)):
        return True
    for d in ("tests", "test"):
        td = root / d
        if td.is_dir() and any(td.rglob("*.py")):
            return True
    return False


def detect_ecosystems(root: Path) -> list[tuple[str, str]]:
    """All detected stacks as (name, default_cmd), ordered by selection priority.
    Python only qualifies with a real pytest signal, so a Rust/Go repo that ships
    a pyproject.toml for bindings is not misread as Python."""
    found: list[tuple[str, str]] = []
    if _has_python_test_signal(root):
        found.append(("python", "pytest"))
    if (root / "go.mod").is_file():
        found.append(("go", "go test ./..."))
    if (root / "Cargo.toml").is_file():
        found.append(("rust", "cargo test"))
    if (root / "pom.xml").is_file():
        found.append(("java-maven", "mvn test"))
    if any((root / f).is_file() for f in ("build.gradle", "build.gradle.kts")):
        cmd = "./gradlew test" if (root / "gradlew").is_file() else "gradle test"
        found.append(("java-gradle", cmd))
    if (root / "Gemfile").is_file():
        found.append(("ruby", "bundle exec rspec"))
    if (root / "composer.json").is_file():
        found.append(("php", "composer test"))
    if (root / "package.json").is_file():
        found.append(("node", f"{_node_runner(root)} test"))
    return found


def resolve(root: Path, override: str | None) -> Resolution:
    candidates: list[str] = []

    # Detect every ecosystem present (for reporting + the default fallback).
    ecosystems = detect_ecosystems(root)
    ecosystem = ecosystems[0][0] if ecosystems else None
    multi_note = None
    if len(ecosystems) > 1:
        multi_note = "Multiple stacks detected: " + ", ".join(n for n, _ in ecosystems)

    if override:
        candidates.append(override)
        return Resolution(override, "flag", ecosystem, str(root), candidates, note=multi_note)

    env = os.environ.get("BUG_SWARM_TEST_CMD")
    if env and env.strip():
        candidates.append(env.strip())
        return Resolution(env.strip(), "env", ecosystem, str(root), candidates, note=multi_note)

    for extractor in (
        from_github_workflows,
        from_gitlab_ci,
        from_makefile,
        from_package_json,
    ):
        hit = extractor(root, candidates)
        if hit:
            cmd, source = hit
            return Resolution(cmd, source, ecosystem, str(root), candidates, note=multi_note)

    if ecosystems:
        name, cmd = ecosystems[0]
        candidates.append(cmd)
        note = "Ecosystem default — confirm it targets the right suite before trusting."
        if multi_note:
            note = f"{note} {multi_note}"
        return Resolution(cmd, f"ecosystem:{name}", name, str(root), candidates, note=note)

    return Resolution(
        None,
        "none",
        ecosystem,
        str(root),
        candidates,
        note="No test command resolvable. Set BUG_SWARM_TEST_CMD or pass --test-cmd.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve the project's test command (env > CI > ecosystem default)."
    )
    parser.add_argument("--repo", default=".", help="Path inside the target repo (default: cwd)")
    parser.add_argument("--test-cmd", default=None, help="Explicit override; wins over all rules")
    parser.add_argument(
        "--require",
        action="store_true",
        help="Exit non-zero if no command resolves (default: report source=none)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    args = parser.parse_args()

    start = Path(args.repo).resolve()
    if not start.exists():
        fail(f"path does not exist: {start}", as_json=args.json)

    root = git_root(start)
    if root is None:
        fail("not a git repository (or git not installed) — bug-swarm needs git", as_json=args.json)

    res = resolve(root, args.test_cmd)

    if res.test_cmd is None and args.require:
        fail(res.note or "no test command resolvable", as_json=args.json)

    if args.json:
        sys.stdout.write(json.dumps({"ok": True, **asdict(res)}, indent=2) + "\n")
    else:
        print(f"test_cmd : {res.test_cmd or '(none)'}")
        print(f"source   : {res.source}")
        print(f"ecosystem: {res.ecosystem or '(unknown)'}")
        print(f"repo_root: {res.repo_root}")
        if res.candidates:
            print(f"considered: {', '.join(dict.fromkeys(res.candidates))}")
        if res.note:
            print(f"note     : {res.note}")

    if res.test_cmd is None:
        sys.exit(0 if not args.require else 1)


if __name__ == "__main__":
    main()
