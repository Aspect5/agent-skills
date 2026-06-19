#!/usr/bin/env python3
"""Resolve the project's test command for bug-swarm, deterministically and portably.

Precedence (first hit wins):
  1. --test-cmd flag (caller override)
  2. $BUG_SWARM_TEST_CMD environment variable
  3. A test step parsed out of CI config (.github/workflows/*.yml, .gitlab-ci.yml,
     Makefile `test:` target, package.json "test" script, pyproject [tool] hints)
  4. An ecosystem default inferred from manifest files present at the repo root
     (pytest / vitest|jest / go test / cargo test / mvn|gradle test / phpunit ...)

The script NEVER guesses silently: it reports WHICH rule fired in the `source`
field so the caller can decide whether to trust it or ask the user. It self-roots
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
    # Strip YAML list markers, leading shell tokens, trailing whitespace.
    cmd = cmd.strip()
    cmd = re.sub(r"^-\s+", "", cmd)
    cmd = re.sub(r"^(run:|sh\s+-c\s+|bash\s+-c\s+)", "", cmd).strip()
    cmd = cmd.strip("'\"").strip()
    return cmd


def from_github_workflows(root: Path, candidates: list[str]) -> tuple[str, str] | None:
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return None
    for wf in sorted(wf_dir.glob("*.y*ml")):
        text = read_text(wf)
        for m in _TEST_LINE.finditer(text):
            cmd = _clean(m.group(0))
            if cmd:
                candidates.append(cmd)
                return cmd, f"ci:.github/workflows/{wf.name}"
    return None


def from_gitlab_ci(root: Path, candidates: list[str]) -> tuple[str, str] | None:
    gl = root / ".gitlab-ci.yml"
    if not gl.is_file():
        return None
    for m in _TEST_LINE.finditer(read_text(gl)):
        cmd = _clean(m.group(0))
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
        # Find a `test:` (or `check:`) target and pull its first recipe line.
        target = re.search(
            r"^(?:test|check)\s*:.*$\n((?:\t.*\n?)+)", text, re.MULTILINE
        )
        if target:
            recipe = target.group(1).splitlines()
            for line in recipe:
                cmd = _clean(line.replace("\t", "", 1))
                cmd = re.sub(r"^@", "", cmd).strip()
                if cmd:
                    candidates.append("make test")
                    # Prefer the portable `make test` over the raw recipe.
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


def ecosystem_default(root: Path, candidates: list[str]) -> tuple[str, str] | None:
    checks: list[tuple[bool, str, str]] = [
        (
            any((root / f).is_file() for f in ("pyproject.toml", "setup.cfg", "tox.ini"))
            or (root / "pytest.ini").is_file(),
            "pytest",
            "python",
        ),
        ((root / "package.json").is_file(), f"{_node_runner(root)} test", "node"),
        ((root / "go.mod").is_file(), "go test ./...", "go"),
        ((root / "Cargo.toml").is_file(), "cargo test", "rust"),
        ((root / "pom.xml").is_file(), "mvn test", "java-maven"),
        (
            any((root / f).is_file() for f in ("build.gradle", "build.gradle.kts")),
            "./gradlew test" if (root / "gradlew").is_file() else "gradle test",
            "java-gradle",
        ),
        ((root / "Gemfile").is_file(), "bundle exec rspec", "ruby"),
        ((root / "composer.json").is_file(), "composer test", "php"),
    ]
    for present, cmd, eco in checks:
        if present:
            candidates.append(cmd)
            return cmd, eco
    return None


def resolve(root: Path, override: str | None, require: bool) -> Resolution:
    candidates: list[str] = []

    # Detect ecosystem regardless of where the command comes from (for reporting).
    eco_hit = ecosystem_default(root, [])
    ecosystem = None
    if eco_hit:
        # eco_hit is (cmd, name); map back to name
        _cmd, name = eco_hit
        ecosystem = name

    if override:
        candidates.append(override)
        return Resolution(override, "flag", ecosystem, str(root), candidates)

    env = os.environ.get("BUG_SWARM_TEST_CMD")
    if env and env.strip():
        candidates.append(env.strip())
        return Resolution(env.strip(), "env", ecosystem, str(root), candidates)

    for extractor in (
        from_github_workflows,
        from_gitlab_ci,
        from_package_json,
        from_makefile,
    ):
        hit = extractor(root, candidates)
        if hit:
            cmd, source = hit
            return Resolution(cmd, source, ecosystem, str(root), candidates)

    eco = ecosystem_default(root, candidates)
    if eco:
        cmd, name = eco
        return Resolution(
            cmd,
            f"ecosystem:{name}",
            name,
            str(root),
            candidates,
            note="Ecosystem default — confirm it targets the right suite before trusting.",
        )

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

    res = resolve(root, args.test_cmd, args.require)

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
