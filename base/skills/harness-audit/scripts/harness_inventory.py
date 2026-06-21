#!/usr/bin/env python3
"""Agent-harness inventory.

Reports what scaffolding *exists* around the model — the six harness components
the harness-audit skill scores: rule files, the tools/MCP surface, guardrails/
hooks, permissions/sandbox config, the static-vs-dynamic context split, and any
observability config — plus a rough always-on context token estimate.

This is deliberately a MAP, not a verdict. Presence is not quality: a present
rule file can still be vague, an absent hook is only a defect if that danger
exists here, and a big always-on context can be justified. The LLM workflow turns
this inventory into the actual audit.

The script self-roots via `git rev-parse --show-toplevel`, so it works from any
working directory inside a repo (pass --repo to override, or it falls back to the
current directory when not in a git repo). It supports --json for machine
consumption and exits non-zero with an explicit message on hard failure.

Token estimate: chars / 4, the standard rough heuristic. It is intentionally
approximate — use it to flag *bands* (lean / heavy / bloated), not to make
precise claims. Thresholds live in references/context-split-signals.md.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

CHARS_PER_TOKEN = 4  # rough industry heuristic; good enough for banding


class InventoryError(Exception):
    """A hard failure that should exit non-zero with a clear message."""


# --- what we look for, by component ----------------------------------------

# Rule files: the agent's standing instructions (root + common nested).
RULE_FILE_NAMES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules")

# Always-on context = root rule files + their always-loaded tool descriptions.
# We approximate always-on as the root-level rule files (nested path-scoped ones
# load only inside their subtree, so they are not paid every turn).
SKILLS_DIRS = (".claude/skills", ".agents/skills", ".codex/skills")
COMMANDS_DIRS = (".claude/commands", ".agents/commands")
PROFILE_DIR = ".agents/profiles"

# Guardrails / hooks.
HOOK_FILES = (
    ".pre-commit-config.yaml",
    ".husky",
    ".githooks",
)
SETTINGS_FILES = (
    ".claude/settings.json",
    ".claude/settings.local.json",
)

# Tools / MCP surface.
MCP_FILES = (
    ".mcp.json",
    "mcp.json",
    ".cursor/mcp.json",
    ".codex/mcp.json",
)

# Observability hints (presence of any of these strings in deps/config).
OBSERVABILITY_HINTS = (
    "logfire",
    "opentelemetry",
    "sentry",
    "langsmith",
    "langfuse",
    "honeycomb",
    "datadog",
)

CI_DIRS = (".github/workflows",)
DEP_MANIFESTS = ("package.json", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod")


@dataclass
class FileEntry:
    path: str
    exists: bool
    bytes: int = 0
    est_tokens: int = 0


@dataclass
class Inventory:
    repo_root: str
    in_git_repo: bool
    rule_files: list[FileEntry] = field(default_factory=list)
    nested_rule_files: list[FileEntry] = field(default_factory=list)
    always_on_est_tokens: int = 0
    always_on_band: str = "unknown"
    skills_dirs: list[FileEntry] = field(default_factory=list)
    commands_dirs: list[FileEntry] = field(default_factory=list)
    profiles: list[str] = field(default_factory=list)
    hook_configs: list[FileEntry] = field(default_factory=list)
    settings_files: list[FileEntry] = field(default_factory=list)
    has_hooks_in_settings: bool = False
    has_permissions_in_settings: bool = False
    mcp_configs: list[FileEntry] = field(default_factory=list)
    mcp_server_count: int = 0
    ci_workflows: list[str] = field(default_factory=list)
    observability_hits: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def resolve_repo_root(repo_arg: str | None) -> tuple[Path, bool]:
    """Self-root: prefer --repo, else the enclosing git toplevel, else cwd."""
    start = Path(repo_arg).resolve() if repo_arg else Path.cwd()
    if not start.exists():
        raise InventoryError(f"--repo path does not exist: {start}")
    try:
        top = run_git(["rev-parse", "--show-toplevel"], start).strip()
        return Path(top), True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Not a git repo (or git missing) — degrade gracefully to the start dir.
        return start, False


def _file_entry(root: Path, rel: str) -> FileEntry:
    p = root / rel
    if p.is_file():
        n = p.stat().st_size
        return FileEntry(path=rel, exists=True, bytes=n, est_tokens=n // CHARS_PER_TOKEN)
    return FileEntry(path=rel, exists=False)


def _dir_entry(root: Path, rel: str) -> FileEntry:
    p = root / rel
    if p.is_dir():
        # count files inside, shallow + recursive, as a size proxy
        count = sum(1 for _ in p.rglob("*") if _.is_file())
        return FileEntry(path=rel, exists=True, bytes=count)  # bytes reused as count
    return FileEntry(path=rel, exists=False)


def _read_text_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _band_for_tokens(tok: int) -> str:
    if tok <= 2000:
        return "lean"
    if tok <= 5000:
        return "heavy"
    return "bloated"


def collect(root: Path, in_git: bool) -> Inventory:
    inv = Inventory(repo_root=str(root), in_git_repo=in_git)

    # 1. Root rule files (the always-on context approximation).
    always_on_chars = 0
    for name in RULE_FILE_NAMES:
        e = _file_entry(root, name)
        inv.rule_files.append(e)
        if e.exists:
            always_on_chars += e.bytes
    inv.always_on_est_tokens = always_on_chars // CHARS_PER_TOKEN
    inv.always_on_band = _band_for_tokens(inv.always_on_est_tokens)

    # Nested (path-scoped) rule files — loaded only inside their subtree.
    if in_git:
        try:
            tracked = run_git(["ls-files"], root).splitlines()
        except subprocess.CalledProcessError:
            tracked = []
    else:
        tracked = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
    for rel in tracked:
        base = os.path.basename(rel)
        if base in RULE_FILE_NAMES and "/" in rel:
            inv.nested_rule_files.append(_file_entry(root, rel))

    # 2. Skills / commands / profiles (the dynamic-context mechanism).
    for d in SKILLS_DIRS:
        e = _dir_entry(root, d)
        if e.exists:
            inv.skills_dirs.append(e)
    for d in COMMANDS_DIRS:
        e = _dir_entry(root, d)
        if e.exists:
            inv.commands_dirs.append(e)
    pdir = root / PROFILE_DIR
    if pdir.is_dir():
        inv.profiles = sorted(p.name for p in pdir.glob("*.md"))

    # 3. Guardrails / hooks.
    for h in HOOK_FILES:
        e = (_dir_entry if (root / h).is_dir() else _file_entry)(root, h)
        if e.exists:
            inv.hook_configs.append(e)
    for s in SETTINGS_FILES:
        e = _file_entry(root, s)
        inv.settings_files.append(e)
        if e.exists:
            txt = _read_text_safe(root / s)
            try:
                data = json.loads(txt) if txt.strip() else {}
            except json.JSONDecodeError:
                data = {}
                inv.notes.append(f"{s} is present but not valid JSON")
            if isinstance(data, dict):
                if data.get("hooks"):
                    inv.has_hooks_in_settings = True
                if data.get("permissions"):
                    inv.has_permissions_in_settings = True

    # 4. Tools / MCP surface.
    for m in MCP_FILES:
        e = _file_entry(root, m)
        if e.exists:
            inv.mcp_configs.append(e)
            txt = _read_text_safe(root / m)
            try:
                data = json.loads(txt) if txt.strip() else {}
                servers = data.get("mcpServers") or data.get("servers") or {}
                if isinstance(servers, dict):
                    inv.mcp_server_count += len(servers)
            except json.JSONDecodeError:
                inv.notes.append(f"{m} is present but not valid JSON")

    # 5. CI workflows.
    for d in CI_DIRS:
        p = root / d
        if p.is_dir():
            inv.ci_workflows = sorted(
                str(f.relative_to(root)) for f in p.glob("*.y*ml") if f.is_file()
            )

    # 6. Observability hints (scan dep manifests for known SDKs).
    hits: set[str] = set()
    for manifest in DEP_MANIFESTS:
        p = root / manifest
        if p.is_file():
            txt = _read_text_safe(p).lower()
            for hint in OBSERVABILITY_HINTS:
                if hint in txt:
                    hits.add(hint)
    # also peek at MCP server names for observability servers
    for m in inv.mcp_configs:
        txt = _read_text_safe(root / m.path).lower()
        for hint in OBSERVABILITY_HINTS:
            if hint in txt:
                hits.add(hint)
    inv.observability_hits = sorted(hits)

    return inv


def _flag_summary(inv: Inventory) -> list[str]:
    """Cheap, non-authoritative prompts for the auditor. Not verdicts."""
    flags: list[str] = []
    if not any(e.exists for e in inv.rule_files):
        flags.append("NO root rule file (AGENTS.md/CLAUDE.md) found — agent runs without a spec.")
    if inv.always_on_band == "bloated":
        flags.append(
            f"Always-on context ~{inv.always_on_est_tokens} tokens (BLOATED band) — "
            "check for dynamic-worthy content / context rot."
        )
    elif inv.always_on_band == "heavy":
        flags.append(
            f"Always-on context ~{inv.always_on_est_tokens} tokens (HEAVY band) — "
            "verify everything in it is genuinely every-task."
        )
    if not inv.hook_configs and not inv.has_hooks_in_settings:
        flags.append("NO hooks/pre-commit detected — correctness may rest on prose alone.")
    if not inv.has_permissions_in_settings and not any(e.exists for e in inv.settings_files):
        flags.append("NO explicit permission/sandbox config — posture may be wide-open by omission.")
    if not inv.observability_hits and not inv.ci_workflows:
        flags.append("NO observability SDK or CI detected — agent runs may be a black box.")
    if inv.mcp_server_count == 0 and not inv.mcp_configs:
        flags.append("No MCP config found — tool surface (if any) is built-in/shell only.")
    return flags


def render_markdown(inv: Inventory, flags: list[str]) -> str:
    lines = ["# Harness inventory", ""]
    lines.append(f"- repo root: `{inv.repo_root}` (git: {inv.in_git_repo})")
    lines.append("")
    lines.append("## Rule files (always-on context approximation)")
    for e in inv.rule_files:
        mark = f"{e.bytes} B ≈ {e.est_tokens} tok" if e.exists else "absent"
        lines.append(f"- `{e.path}` — {mark}")
    lines.append(
        f"- **always-on estimate: ~{inv.always_on_est_tokens} tokens "
        f"({inv.always_on_band} band)**"
    )
    if inv.nested_rule_files:
        lines.append(f"- nested (path-scoped) rule files: {len(inv.nested_rule_files)}")
        for e in inv.nested_rule_files:
            lines.append(f"  - `{e.path}` (≈ {e.est_tokens} tok, loaded only in subtree)")
    lines.append("")
    lines.append("## Dynamic-context mechanism")
    lines.append(f"- skills dirs: {[e.path for e in inv.skills_dirs] or 'none'}")
    lines.append(f"- commands dirs: {[e.path for e in inv.commands_dirs] or 'none'}")
    lines.append(f"- profiles: {inv.profiles or 'none'}")
    lines.append("")
    lines.append("## Guardrails / hooks")
    lines.append(f"- hook configs: {[e.path for e in inv.hook_configs] or 'none'}")
    lines.append(f"- hooks in settings.json: {inv.has_hooks_in_settings}")
    lines.append("")
    lines.append("## Tools / MCP surface")
    lines.append(f"- MCP configs: {[e.path for e in inv.mcp_configs] or 'none'}")
    lines.append(f"- declared MCP servers: {inv.mcp_server_count}")
    lines.append("")
    lines.append("## Permissions / sandbox")
    lines.append(f"- settings files present: {[e.path for e in inv.settings_files if e.exists] or 'none'}")
    lines.append(f"- permissions block in settings: {inv.has_permissions_in_settings}")
    lines.append("")
    lines.append("## Observability")
    lines.append(f"- SDK/server hints: {inv.observability_hits or 'none detected'}")
    lines.append(f"- CI workflows: {inv.ci_workflows or 'none'}")
    if inv.notes:
        lines.append("")
        lines.append("## Notes")
        for n in inv.notes:
            lines.append(f"- {n}")
    lines.append("")
    lines.append("## Non-authoritative flags (prompts, NOT verdicts)")
    if flags:
        for f in flags:
            lines.append(f"- {f}")
    else:
        lines.append("- (none) — presence looks complete; quality still needs the audit.")
    lines.append("")
    lines.append("_Presence is not quality. This is a map for the harness-audit skill, not a score._")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inventory a repo's agent harness (presence/size of rule files, "
        "skills, hooks, MCP/permission config, CI, observability)."
    )
    parser.add_argument("--repo", help="Path inside the repo (default: self-root via git)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown")
    args = parser.parse_args(argv)

    try:
        root, in_git = resolve_repo_root(args.repo)
        inv = collect(root, in_git)
    except InventoryError as exc:
        print(f"harness_inventory: {exc}", file=sys.stderr)
        return 2

    flags = _flag_summary(inv)

    if args.json:
        payload = asdict(inv)
        payload["flags"] = flags
        print(json.dumps(payload, indent=2))
    else:
        print(render_markdown(inv, flags))
    return 0


if __name__ == "__main__":
    sys.exit(main())
