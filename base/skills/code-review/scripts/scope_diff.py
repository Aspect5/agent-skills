#!/usr/bin/env python3
"""Scope a review diff: enumerate changed files, classify them, and attach
per-file patch text.

Project-agnostic. Self-roots via `git rev-parse --show-toplevel` so it works from
any subdirectory of any repo. Used by the `code-review` skill to drive risk-tiered
reviewer dispatch deterministically instead of by eyeball.

What it does
------------
1. Resolve the repo root (no cwd assumptions).
2. Resolve a diff range:
     - explicit --base/--head, OR
     - a PR-style base..head when --base looks like a ref, OR
     - the working-tree diff (staged + unstaged) against HEAD when no base given.
3. For each changed file emit: path, status (A/M/D/R), added/deleted line counts,
   a coarse `category` (source / test / migration / lockfile / generated / vendored /
   doc / config / asset / other), and `review_relevant` (whether a human-quality
   reviewer should read the patch). Lockfiles/vendored/generated/binary are flagged
   low-signal but NOT dropped from the listing — the caller decides; migrations are
   always kept and never marked low-signal.
4. Optionally include the unified patch text per file (--patch).
5. Emit a compact risk summary: total files, added/deleted lines, a suggested
   review tier (trivial / standard / full), and the set of risky-path hits.

Exit codes
----------
0  success
2  not inside a git work tree / git invocation failed
3  bad arguments / unresolvable diff range

Determinism
-----------
No network, no LLM, stdlib only. Classification is pattern-based and explicit;
there are no magic numbers without a named constant + rationale.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import PurePosixPath

# ---------------------------------------------------------------------------
# Tier thresholds. Named, not magic. A reviewer/profile may override via flags.
# ---------------------------------------------------------------------------
TRIVIAL_MAX_CHANGED_LINES = 10  # <= this many added+deleted lines => 1-2 reviewers
STANDARD_MAX_CHANGED_LINES = 100  # <= this => 3-4 reviewers; above => full fan-out
FULL_FILE_COUNT = 50  # >= this many files => full fan-out regardless of line count

# ---------------------------------------------------------------------------
# Classification patterns. Substring/suffix/regex against the POSIX path.
# These are heuristics across ecosystems; a project profile can refine via the
# skill, but the skill must run usefully with zero config — hence sane defaults.
# ---------------------------------------------------------------------------
LOCKFILE_BASENAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "npm-shrinkwrap.json",
    "poetry.lock",
    "Pipfile.lock",
    "uv.lock",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
    "Gemfile.lock",
    "bun.lockb",
    "flake.lock",
}

# Directory segments that mark vendored / third-party / build output.
VENDORED_SEGMENTS = (
    "node_modules",
    "vendor",
    "third_party",
    "third-party",
    ".venv",
    "venv",
    "dist",
    "build",
    "out",
    ".next",
    "target",
    "__pycache__",
    ".terraform",
)

# Generated-file signals (suffix or basename). `.generated.` covers the common
# `*.generated.ts` / `api.generated.ts` convention; protobuf/grpc stubs too.
GENERATED_SUFFIXES = (
    ".generated.ts",
    ".generated.tsx",
    ".generated.js",
    ".g.dart",
    "_pb2.py",
    "_pb2_grpc.py",
    ".pb.go",
)
GENERATED_BASENAME_HINTS = (
    "api.generated.ts",
    "schema.generated",
)

# Migration directories — KEPT and always review-relevant (schema is high risk).
MIGRATION_SEGMENTS = ("migrations", "migration")

# Test file signals.
TEST_SEGMENTS = ("tests", "test", "__tests__", "spec", "e2e")
TEST_SUFFIXES = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    "_test.py",
    "_test.go",
    "test_.py",  # prefix handled separately; kept for documentation
)
TEST_BASENAME_RE = re.compile(r"(^test_.*\.py$)|(.*_test\.(py|go)$)|(.*\.(test|spec)\.[jt]sx?$)")

DOC_SUFFIXES = (".md", ".mdx", ".rst", ".txt", ".adoc")
CONFIG_SUFFIXES = (
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".json",
    ".env",
    ".properties",
)
ASSET_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".mp4",
    ".mov",
    ".zip",
    ".gz",
)
SOURCE_SUFFIXES = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".rb",
    ".php",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".swift",
    ".scala",
    ".sql",
    ".sh",
    ".bash",
)

# Risky paths: a hit forces full review regardless of size. Generic across repos.
RISKY_PATH_SUBSTRINGS = (
    "migration",
    "schema",
    "auth",
    "security",
    "/secrets",
    "credential",
    "Dockerfile",
    "dockerfile",
    ".github/workflows",
    ".github/scripts",
    "cloudbuild",
    "ci-check",
    "/policy",
    "rls",
    "permission",
    "token",
    "/.env",
    "payment",
    "billing",
    "crypto",
)


@dataclass
class FileChange:
    path: str
    status: str  # A/M/D/R/...
    added: int
    deleted: int
    category: str
    review_relevant: bool
    risky_hits: list[str] = field(default_factory=list)
    patch: str | None = None

    def as_dict(self, include_patch: bool) -> dict[str, object]:
        d: dict[str, object] = {
            "path": self.path,
            "status": self.status,
            "added": self.added,
            "deleted": self.deleted,
            "category": self.category,
            "review_relevant": self.review_relevant,
            "risky_hits": self.risky_hits,
        }
        if include_patch:
            d["patch"] = self.patch
        return d


class GitError(RuntimeError):
    pass


def run_git(args: list[str], cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:  # git not installed
        raise GitError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise GitError(f"git {' '.join(args)} failed: {stderr}") from exc
    return result.stdout


def repo_root() -> str:
    # Self-root: never assume cwd is the repo root.
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise GitError("not inside a git work tree (git rev-parse --show-toplevel failed)") from exc
    if not out:
        raise GitError("git rev-parse --show-toplevel returned empty output")
    return out


def _segments(path: str) -> tuple[str, ...]:
    return PurePosixPath(path).parts


def _basename(path: str) -> str:
    return PurePosixPath(path).name


def classify(path: str) -> tuple[str, bool]:
    """Return (category, review_relevant)."""
    segs = _segments(path)
    base = _basename(path)
    lower = path.lower()

    # Migrations first — highest risk, always relevant, even if also .sql/.py.
    if any(seg in MIGRATION_SEGMENTS for seg in segs):
        return "migration", True

    # Lockfiles: relevant to security (supply chain) but the diff is noise.
    if base in LOCKFILE_BASENAMES:
        return "lockfile", False

    # Vendored / build output.
    if any(seg in VENDORED_SEGMENTS for seg in segs):
        return "vendored", False

    # Generated code.
    if any(lower.endswith(suf) for suf in GENERATED_SUFFIXES) or any(
        hint in lower for hint in GENERATED_BASENAME_HINTS
    ):
        return "generated", False

    # Tests.
    if TEST_BASENAME_RE.match(base) or any(seg in TEST_SEGMENTS for seg in segs):
        # A test directory or a test-shaped basename. Relevant (test quality matters).
        return "test", True

    # Docs.
    if any(lower.endswith(suf) for suf in DOC_SUFFIXES):
        return "doc", True

    # Binary / asset — not human-readable diffs.
    if any(lower.endswith(suf) for suf in ASSET_SUFFIXES):
        return "asset", False

    # Source code.
    if any(lower.endswith(suf) for suf in SOURCE_SUFFIXES):
        return "source", True

    # Config (after source/doc so .sql/.sh win as source).
    if any(lower.endswith(suf) for suf in CONFIG_SUFFIXES):
        return "config", True

    # Dockerfiles, Makefiles, CI YAML caught above by config; everything else.
    return "other", True


def risky_hits(path: str) -> list[str]:
    lower = path.lower()
    return [marker for marker in RISKY_PATH_SUBSTRINGS if marker.lower() in lower]


def resolve_range(base: str | None, head: str | None) -> tuple[list[str], str]:
    """Return (numstat_args, mode_label).

    No base => working tree (HEAD..worktree, including staged+unstaged).
    base + head => base...head (merge-base diff, the PR-review semantics).
    base only => base...HEAD.
    """
    if base is None and head is None:
        return (["diff", "--numstat", "HEAD"], "worktree")
    if base is not None and head is not None:
        return (["diff", "--numstat", f"{base}...{head}"], f"{base}...{head}")
    if base is not None:
        return (["diff", "--numstat", f"{base}...HEAD"], f"{base}...HEAD")
    raise GitError("--head requires --base")


def patch_range(base: str | None, head: str | None, path: str) -> list[str]:
    if base is None and head is None:
        return ["diff", "HEAD", "--", path]
    if base is not None and head is not None:
        return ["diff", f"{base}...{head}", "--", path]
    return ["diff", f"{base}...HEAD", "--", path]


def parse_numstat(raw: str) -> list[tuple[int, int, str]]:
    rows: list[tuple[int, int, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_s, del_s, path = parts[0], parts[1], parts[-1]
        # Renames render as "old => new" or with {a => b} braces; take the new path.
        if "=>" in path:
            path = re.sub(r"\{[^}]*=>\s*([^}]*)\}", r"\1", path)
            if "=>" in path:
                path = path.split("=>")[-1].strip()
            path = path.replace("//", "/").strip()
        added = 0 if add_s == "-" else int(add_s)
        deleted = 0 if del_s == "-" else int(del_s)
        rows.append((added, deleted, path))
    return rows


def status_for(root: str, base: str | None, head: str | None, path: str) -> str:
    args = ["diff", "--name-status"]
    if base is not None and head is not None:
        args.append(f"{base}...{head}")
    elif base is not None:
        args.append(f"{base}...HEAD")
    else:
        args.append("HEAD")
    args.extend(["--", path])
    out = run_git(args, root)
    for line in out.splitlines():
        cols = line.split("\t")
        if cols and cols[0]:
            return cols[0][0]  # first char: A/M/D/R/C
    return "M"


def build_changes(
    root: str, base: str | None, head: str | None, include_patch: bool
) -> list[FileChange]:
    numstat_args, _ = resolve_range(base, head)
    rows = parse_numstat(run_git(numstat_args, root))
    changes: list[FileChange] = []
    for added, deleted, path in rows:
        category, relevant = classify(path)
        hits = risky_hits(path)
        change = FileChange(
            path=path,
            status=status_for(root, base, head, path),
            added=added,
            deleted=deleted,
            category=category,
            review_relevant=relevant,
            risky_hits=hits,
        )
        if include_patch and relevant:
            change.patch = run_git(patch_range(base, head, path), root)
        changes.append(change)
    # Stable, useful ordering: risky first, then source, then by size.
    category_rank = {
        "migration": 0,
        "source": 1,
        "config": 2,
        "test": 3,
        "doc": 4,
        "generated": 5,
        "lockfile": 6,
        "vendored": 7,
        "asset": 8,
        "other": 9,
    }
    changes.sort(
        key=lambda c: (
            0 if c.risky_hits else 1,
            category_rank.get(c.category, 9),
            -(c.added + c.deleted),
            c.path,
        )
    )
    return changes


def suggest_tier(changes: list[FileChange]) -> str:
    relevant = [c for c in changes if c.review_relevant]
    total_lines = sum(c.added + c.deleted for c in relevant)
    file_count = len(relevant)
    any_risky = any(c.risky_hits for c in changes)
    if any_risky or file_count >= FULL_FILE_COUNT or total_lines > STANDARD_MAX_CHANGED_LINES:
        return "full"
    if total_lines <= TRIVIAL_MAX_CHANGED_LINES:
        return "trivial"
    return "standard"


def summarize(changes: list[FileChange], mode: str) -> dict[str, object]:
    relevant = [c for c in changes if c.review_relevant]
    risky = sorted({h for c in changes for h in c.risky_hits})
    return {
        "mode": mode,
        "total_files": len(changes),
        "review_relevant_files": len(relevant),
        "low_signal_files": len(changes) - len(relevant),
        "added_lines": sum(c.added for c in relevant),
        "deleted_lines": sum(c.deleted for c in relevant),
        "categories": _category_counts(changes),
        "risky_markers": risky,
        "suggested_tier": suggest_tier(changes),
    }


def _category_counts(changes: list[FileChange]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in changes:
        counts[c.category] = counts.get(c.category, 0) + 1
    return dict(sorted(counts.items()))


def print_markdown(changes: list[FileChange], summary: dict[str, object]) -> None:
    print("# Review scope")
    print()
    print(f"- Mode: `{summary['mode']}`")
    print(
        f"- Files: {summary['total_files']} "
        f"({summary['review_relevant_files']} review-relevant, "
        f"{summary['low_signal_files']} low-signal)"
    )
    print(f"- Lines: +{summary['added_lines']} / -{summary['deleted_lines']}")
    print(f"- Suggested tier: **{summary['suggested_tier']}**")
    if summary["risky_markers"]:
        print(f"- Risky markers: {', '.join(summary['risky_markers'])}")  # type: ignore[arg-type]
    print()
    print("| File | Status | +/- | Category | Relevant | Risky |")
    print("|---|:--:|---:|---|:--:|---|")
    for c in changes:
        risky = ",".join(c.risky_hits) if c.risky_hits else ""
        rel = "yes" if c.review_relevant else "no"
        print(
            f"| `{c.path}` | {c.status} | +{c.added}/-{c.deleted} | "
            f"{c.category} | {rel} | {risky} |"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scope a review diff for the code-review skill.")
    parser.add_argument("--base", default=None, help="Base ref (e.g. origin/main). Omit for worktree diff.")
    parser.add_argument("--head", default=None, help="Head ref (defaults to HEAD when --base is set).")
    parser.add_argument("--patch", action="store_true", help="Include per-file patch text.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    args = parser.parse_args()

    try:
        root = repo_root()
        changes = build_changes(root, args.base, args.head, include_patch=args.patch)
    except GitError as exc:
        msg = str(exc)
        print(f"error: {msg}", file=sys.stderr)
        # Distinguish "not a repo / git failed" (2) from arg-shaped problems (3).
        if "requires --base" in msg:
            return 3
        return 2

    _, mode = resolve_range(args.base, args.head)
    summary = summarize(changes, mode)

    if args.json:
        print(
            json.dumps(
                {
                    "summary": summary,
                    "files": [c.as_dict(include_patch=args.patch) for c in changes],
                },
                indent=2,
            )
        )
        return 0

    print_markdown(changes, summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
