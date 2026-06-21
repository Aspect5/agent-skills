#!/usr/bin/env python3
"""Reference fail-closed guardrail check for the `guardrail-author` skill.

A single, self-rooting, dependency-light (stdlib + git only) deterministic check
that a generated hook can call directly. It implements the three canonical danger
surfaces from the catalog — `secret`, `protected-branch`, `destructive-command` —
plus `--detect-harness` so Step 0 can resolve which harness is in play.

The whole point is DETERMINISM and FAIL-CLOSED behavior: this is code that runs at
a lifecycle point, not a prompt the model can forget. The exit code IS the verdict.

Exit-code contract (the universal hook convention)
--------------------------------------------------
  0   ALLOW   — no danger found; the action may proceed.
  1   BLOCK   — danger found; the tool call / commit / job must stop.
  2   ERROR   — the check could not run cleanly (bad args, git failure,
                unreadable input). FAIL CLOSED: a non-zero code blocks. A guardrail
                that cannot evaluate must never silently allow.

So both "found danger" and "could not check" are non-zero — a hook wired to this
script blocks in either case, which is the fail-closed guarantee.

Modes
-----
  --mode secret              scan content for credential-shaped strings
  --mode protected-branch    block force/direct push to a protected branch
  --mode destructive-command block rm -rf outside the workspace, DROP TABLE, etc.
  --mode pre-tool            dispatch protected-branch + destructive on a command
                             (the shape a Claude Code / Codex PreToolUse hook uses)
  --detect-harness           report which agent harness(es) this repo wires (JSON)

Input sources (first present wins), per mode:
  secret:   --path FILE (repeatable) | --staged (git staged blobs) |
            --range A...B (diff content) | --stdin (raw content) |
            positional files
  protected-branch / destructive / pre-tool:
            --command "<cmd>" | $CLAUDE_TOOL_COMMAND / $TOOL_COMMAND | --stdin |
            (pre-tool) a JSON tool payload on stdin with a `.command` field

--json emits a structured verdict on stdout in addition to the exit code.

Everything here is intentionally conservative and documented; patterns are starting
points a profile refines (`secret_patterns`, `protected_branches`,
`destructive_patterns`). This script never prints a matched secret value — only a
redacted form.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

# Exit codes — the verdict surface.
ALLOW = 0
BLOCK = 1
ERROR = 2  # fail-closed: still non-zero, still blocks.

# ---------------------------------------------------------------------------
# Secret patterns. High-confidence, provider-prefixed shapes keep false
# positives low; the generic high-entropy assignment is gated behind an entropy
# threshold. A profile's `secret_patterns` extends this set.
# ---------------------------------------------------------------------------
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[posru]_[A-Za-z0-9]{36,}\b")),
    ("github-fine-grained", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("gitlab-pat", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    # Generic assignment to a secret-named variable — only fires above the entropy gate.
    (
        "generic-secret-assignment",
        re.compile(
            r"""(?ix)
            \b(?:api[_-]?key|secret|token|passwd|password|private[_-]?key|access[_-]?key)\b
            \s*[:=]\s*
            ['"]?(?P<val>[A-Za-z0-9+/_\-]{16,})['"]?
            """
        ),
    ),
)

# Known-dummy / placeholder values that must NEVER be flagged (the false-block set).
PLACEHOLDER_VALUES = {
    "akiaiosfodnn7example",  # AWS's own documented dummy
    "your-key-here",
    "your-token-here",
    "your-secret-here",
    "changeme",
    "change-me",
    "replace-me",
    "example",
    "placeholder",
    "dummy",
    "test",
    "fake",
    "xxxxxxxx",
    "redacted",
    "none",
    "null",
}

# Path stems that conventionally hold placeholders, never real secrets.
PLACEHOLDER_PATH_HINTS = (
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.dist",
    "sample.env",
)

# Shannon-entropy floor for the generic-assignment match (bits/char). Low-entropy
# values (words, obvious dummies) fall below it and are not flagged.
GENERIC_ENTROPY_MIN = 3.2

# ---------------------------------------------------------------------------
# Protected branches. A profile's `protected_branches` overrides this default.
# ---------------------------------------------------------------------------
DEFAULT_PROTECTED = ("main", "master", "staging", "production", "prod")
DEFAULT_PROTECTED_GLOBS = (re.compile(r"^release/"), re.compile(r"^hotfix/"))

# ---------------------------------------------------------------------------
# Destructive command patterns. Each returns a reason when it matches.
# ---------------------------------------------------------------------------
DESTRUCTIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("drop-database", re.compile(r"(?i)\bDROP\s+(DATABASE|SCHEMA)\b")),
    ("drop-table", re.compile(r"(?i)\bDROP\s+TABLE\b")),
    ("truncate", re.compile(r"(?i)\bTRUNCATE\s+TABLE\b")),
    ("chmod-777-recursive", re.compile(r"\bchmod\s+-[A-Za-z]*R[A-Za-z]*\s+0?777\b")),
    ("dd-to-device", re.compile(r"\bdd\b[^\n]*\bof=/dev/")),
    ("fork-bomb", re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:")),
    ("pipe-to-shell", re.compile(r"(?i)\bcurl\b[^\n|]*\|\s*(sudo\s+)?(ba)?sh\b")),
    ("git-clean-fdx", re.compile(r"\bgit\s+clean\b[^\n]*-[a-z]*f[a-z]*d[a-z]*x")),
    ("terraform-destroy", re.compile(r"\bterraform\s+destroy\b")),
    ("kubectl-delete-all", re.compile(r"\bkubectl\s+delete\b[^\n]*--all\b")),
)

# rm -rf is handled specially (scope-resolved), not as a flat regex.
RM_RF_RE = re.compile(r"\brm\s+(?:-[A-Za-z]*\s+)*-?[A-Za-z]*r[A-Za-z]*f[A-Za-z]*\b|"
                      r"\brm\s+(?:-[A-Za-z]*\s+)*-?[A-Za-z]*f[A-Za-z]*r[A-Za-z]*\b")


class GuardrailError(RuntimeError):
    """A fatal, explained error → exit ERROR (fail closed)."""


@dataclass
class Verdict:
    allowed: bool
    mode: str
    reasons: list[str] = field(default_factory=list)
    details: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "mode": self.mode,
            "reasons": self.reasons,
            "details": self.details,
        }


# --------------------------------------------------------------------------- git

def run_git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise GuardrailError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        msg = (exc.stderr or "").strip() or f"git {' '.join(args)} failed"
        raise GuardrailError(msg) from exc
    return result.stdout


def repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise GuardrailError("not inside a git work tree") from exc
    if not out:
        raise GuardrailError("git rev-parse --show-toplevel returned empty")
    return Path(out)


# --------------------------------------------------------------------------- util

def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    from math import log2
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * log2(c / n) for c in counts.values())


def redact(value: str) -> str:
    """Show only enough to identify, never the secret. e.g. ghp_ABCD…(36)."""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:4]}…({len(value)})"


# --------------------------------------------------------------------------- secret mode

def is_placeholder(value: str) -> bool:
    low = value.lower()
    if low in PLACEHOLDER_VALUES:
        return True
    # all-x / all-same-char dummies, and "your-..." style.
    if re.fullmatch(r"[x]{4,}", low):
        return True
    if low.startswith(("your-", "my-", "the-")) or low.endswith(("-here", "-goes-here")):
        return True
    return False


def path_is_placeholder_file(name: str | None) -> bool:
    if not name:
        return False
    base = PurePosixPath(name).name.lower()
    return any(h in name.lower() or base == h for h in PLACEHOLDER_PATH_HINTS)


def scan_secret(content: str, source_name: str | None, allowlist: set[str]) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    if source_name and (source_name in allowlist or path_is_placeholder_file(source_name)):
        return hits
    for kind, pat in SECRET_PATTERNS:
        for m in pat.finditer(content):
            val = m.group("val") if "val" in pat.groupindex else m.group(0)
            if is_placeholder(val):
                continue
            if kind == "generic-secret-assignment":
                # Gate the noisy generic case behind entropy.
                if shannon_entropy(val) < GENERIC_ENTROPY_MIN:
                    continue
            hits.append({
                "kind": kind,
                "source": source_name or "<stdin>",
                "match": redact(val),  # NEVER the raw value
            })
    return hits


def gather_secret_content(args: argparse.Namespace, root: Path) -> list[tuple[str | None, str]]:
    sources: list[tuple[str | None, str]] = []
    if args.stdin:
        sources.append((args.name, sys.stdin.read()))
    for p in list(args.path or []) + list(args.files or []):
        try:
            sources.append((p, Path(p).read_text(errors="replace")))
        except OSError as exc:
            raise GuardrailError(f"cannot read {p}: {exc}") from exc
    if args.staged:
        names = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACM"], root).split()
        for name in names:
            try:
                blob = run_git(["show", f":{name}"], root)
            except GuardrailError:
                continue  # deleted/binary staged entry — skip content
            sources.append((name, blob))
    if args.range:
        diff = run_git(["diff", args.range], root)
        added = "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
        sources.append((f"diff:{args.range}", added))
    if not sources:
        raise GuardrailError("secret mode: no input (use --staged, --range, --path, or --stdin)")
    return sources


def mode_secret(args: argparse.Namespace, root: Path) -> Verdict:
    allowlist = set(args.allow or [])
    sources = gather_secret_content(args, root)
    all_hits: list[dict[str, object]] = []
    for name, content in sources:
        all_hits.extend(scan_secret(content, name, allowlist))
    if all_hits:
        reasons = [f"secret-shaped string ({h['kind']}) in {h['source']} [{h['match']}]" for h in all_hits]
        return Verdict(False, "secret", reasons, all_hits)
    return Verdict(True, "secret")


# --------------------------------------------------------------------------- command sourcing

def get_command(args: argparse.Namespace) -> str:
    if args.command:
        return args.command
    env = os.environ.get("CLAUDE_TOOL_COMMAND") or os.environ.get("TOOL_COMMAND")
    if env:
        return env
    if args.stdin:
        raw = sys.stdin.read().strip()
        # A PreToolUse payload may be JSON with a .command field; tolerate raw too.
        if raw.startswith("{"):
            try:
                obj = json.loads(raw)
                for key in ("command", "tool_input", "input"):
                    v = obj.get(key) if isinstance(obj, dict) else None
                    if isinstance(v, str):
                        return v
                    if isinstance(v, dict) and isinstance(v.get("command"), str):
                        return v["command"]
            except json.JSONDecodeError:
                pass
        return raw
    raise GuardrailError("command mode: no command (use --command, $CLAUDE_TOOL_COMMAND, or --stdin)")


# --------------------------------------------------------------------------- protected-branch

def protected_set(args: argparse.Namespace) -> tuple[set[str], tuple[re.Pattern[str], ...]]:
    if args.protected:
        return set(args.protected), DEFAULT_PROTECTED_GLOBS
    return set(DEFAULT_PROTECTED), DEFAULT_PROTECTED_GLOBS


def is_protected(ref: str, names: set[str], globs: tuple[re.Pattern[str], ...]) -> bool:
    short = ref.split("/")[-1] if ref.startswith("refs/") else ref
    short = short.removeprefix("origin/")
    if short in names:
        return True
    return any(g.search(short) for g in globs)


def mode_protected_branch(command: str, args: argparse.Namespace) -> Verdict:
    names, globs = protected_set(args)
    if not re.search(r"\bgit\s+push\b", command):
        return Verdict(True, "protected-branch")
    force = bool(re.search(r"(--force\b|--force-with-lease\b|(^|\s)-[a-zA-Z]*f[a-zA-Z]*(\s|$))", command))
    # Pull out an explicit "remote branch" target after the push tokens.
    toks = command.split()
    targets = [t for t in toks[toks.index("push") + 1:] if not t.startswith("-")] if "push" in toks else []
    # Drop the remote (first positional) to inspect the refspec(s).
    refs = targets[1:] if len(targets) >= 2 else targets
    hit = next((r for r in refs if is_protected(r.split(":")[-1], names, globs)), None)
    if hit and (force or args.block_direct_push):
        verb = "force-push" if force else "direct push"
        return Verdict(False, "protected-branch",
                       [f"{verb} to protected branch '{hit}' blocked — open a PR instead"])
    # Honesty about a residual blind spot: a force-push with NO explicit refspec
    # (`git push -f`) targets the upstream tracking branch, which may be protected,
    # but the command string carries no ref token to match. We do NOT block (that
    # would false-block a legit `git push -f origin feature`); instead we surface an
    # advisory so the caller knows the command parser alone cannot cover this case —
    # a pre-push hook (resolved dest ref on stdin) or server-side protection must.
    if force and not refs:
        return Verdict(
            True, "protected-branch",
            details=[{
                "advisory": "force-push with no explicit refspec — target resolves "
                            "to the upstream branch, which the command parser cannot "
                            "see. Cover at the pre-push hook or server-side, not here.",
            }],
        )
    return Verdict(True, "protected-branch")


# --------------------------------------------------------------------------- destructive

def rm_rf_escapes_workspace(command: str, root: Path) -> str | None:
    """Return a reason if an rm -rf targets a path outside the workspace, else None."""
    if not RM_RF_RE.search(command):
        return None
    # Extract operands after rm (drop flags).
    after = command[command.index("rm"):]
    toks = after.split()
    operands = [t for t in toks[1:] if not t.startswith("-")]
    for op in operands:
        expanded = os.path.expandvars(os.path.expanduser(op))
        # Dangerous absolutes / home / parent escapes.
        if expanded in ("/", "/*", "~", os.path.expanduser("~")):
            return f"rm -rf targets '{op}' (filesystem/home root)"
        if expanded.startswith("/") :
            try:
                resolved = Path(expanded).resolve()
                resolved.relative_to(root.resolve())
            except (ValueError, OSError):
                return f"rm -rf targets '{op}' outside the workspace ({root})"
        if op.startswith("..") or "/../" in op:
            return f"rm -rf escapes the workspace via '{op}'"
    return None


def mode_destructive(command: str, root: Path) -> Verdict:
    reasons: list[str] = []
    rm = rm_rf_escapes_workspace(command, root)
    if rm:
        reasons.append(rm)
    for kind, pat in DESTRUCTIVE_PATTERNS:
        if pat.search(command):
            reasons.append(f"destructive command ({kind})")
    if reasons:
        return Verdict(False, "destructive-command", reasons)
    return Verdict(True, "destructive-command")


# --------------------------------------------------------------------------- harness detection

def detect_harness(root: Path) -> dict[str, object]:
    def exists(rel: str) -> bool:
        return (root / rel).exists()

    found: list[str] = []
    detail: dict[str, object] = {}
    if exists(".claude/settings.json") or exists(".claude/settings.local.json"):
        found.append("claude-code")
        detail["claude_settings"] = [
            p for p in (".claude/settings.json", ".claude/settings.local.json") if exists(p)
        ]
    if exists(".pre-commit-config.yaml"):
        found.append("pre-commit")
    if (root / ".git" / "hooks").is_dir():
        hooks = [h.name for h in (root / ".git" / "hooks").glob("*") if not h.name.endswith(".sample")]
        if hooks:
            found.append("git-hooks")
            detail["git_hooks"] = hooks
    if exists(".codex") or exists("codex.toml"):
        found.append("codex")
    ci: list[str] = []
    if (root / ".github" / "workflows").is_dir():
        ci.append("github-actions")
    for f in ("cloudbuild.yaml", "cloudbuild.yml", ".gitlab-ci.yml", ".circleci/config.yml", "azure-pipelines.yml"):
        if exists(f):
            ci.append(f)
    if ci:
        found.append("ci")
        detail["ci"] = ci
    return {"harnesses": found, "detail": detail}


# --------------------------------------------------------------------------- main

def emit(verdict: Verdict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(verdict.as_dict(), indent=2))
    if verdict.allowed:
        if not as_json:
            print(f"ALLOW [{verdict.mode}]")
        return ALLOW
    # Block: actionable message on stderr (the hook surfaces this).
    for r in verdict.reasons:
        print(f"BLOCKED [{verdict.mode}]: {r}", file=sys.stderr)
    if not as_json and not verdict.reasons:
        print(f"BLOCKED [{verdict.mode}]", file=sys.stderr)
    return BLOCK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed guardrail check (guardrail-author skill).")
    parser.add_argument("--mode", choices=["secret", "protected-branch", "destructive-command", "pre-tool"])
    parser.add_argument("--detect-harness", action="store_true", help="Report wired harness(es) as JSON and exit.")
    parser.add_argument("--json", action="store_true")
    # secret inputs
    parser.add_argument("--path", action="append", help="File to scan (repeatable).")
    parser.add_argument("files", nargs="*", help="Positional files to scan.")
    parser.add_argument("--staged", action="store_true", help="Scan git staged blobs.")
    parser.add_argument("--range", help="Scan added lines of a diff range A...B.")
    parser.add_argument("--stdin", action="store_true", help="Read content/command from stdin.")
    parser.add_argument("--name", help="Logical name for --stdin content (for allowlist/path hints).")
    parser.add_argument("--allow", action="append", help="Allowlisted path that may contain secrets (repeatable).")
    # command inputs
    parser.add_argument("--command", help="Command string to evaluate.")
    parser.add_argument("--pre-push", action="store_true", help="(protected-branch) reserved: pre-push hook context.")
    parser.add_argument("--block-direct-push", action="store_true", help="Block ANY push to a protected branch (PR-only policy).")
    parser.add_argument("--protected", action="append", help="Protected branch name (repeatable; overrides defaults).")
    args = parser.parse_args(argv)

    try:
        root = repo_root()
    except GuardrailError as exc:
        # Even harness detection needs a repo; fail closed with a clear message.
        print(f"error: {exc}", file=sys.stderr)
        return ERROR

    try:
        if args.detect_harness:
            print(json.dumps(detect_harness(root), indent=2))
            return ALLOW  # detection is informational, not a gate.

        if not args.mode:
            raise GuardrailError("--mode is required (or use --detect-harness)")

        if args.mode == "secret":
            verdict = mode_secret(args, root)
        elif args.mode == "protected-branch":
            verdict = mode_protected_branch(get_command(args), args)
        elif args.mode == "destructive-command":
            verdict = mode_destructive(get_command(args), root)
        else:  # pre-tool: a command gate runs both command checks.
            cmd = get_command(args)
            pb = mode_protected_branch(cmd, args)
            de = mode_destructive(cmd, root)
            allowed = pb.allowed and de.allowed
            verdict = Verdict(allowed, "pre-tool", pb.reasons + de.reasons, pb.details + de.details)
    except GuardrailError as exc:
        # FAIL CLOSED: any inability to evaluate blocks with exit ERROR.
        print(f"error: {exc}", file=sys.stderr)
        return ERROR

    return emit(verdict, args.json)


if __name__ == "__main__":
    sys.exit(main())
