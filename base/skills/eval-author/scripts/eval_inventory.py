#!/usr/bin/env python3
"""Verification-coverage inventory for the eval-author skill.

Answers one deterministic question before any judgment happens: *what in this
repo is verified, and what is not?* It does NOT decide whether a thing is
verified WELL — that is the LLM's job. It produces the honest denominator the
skill reports against, so coverage can never be asserted from a vibe.

Two surfaces, because the New-SDLC framework distinguishes them:

  - DETERMINISTIC surfaces  -> verified by TESTS  (input X -> output Y).
    Heuristic: source modules/functions that have no co-located or
    name-matching test.
  - NON-DETERMINISTIC surfaces -> verified by EVALS (trajectory / generated
    output, scored by a rubric or an LM judge). Heuristic: files that touch an
    LLM/agent/prompt surface (import an LLM SDK, define a prompt/agent/tool, or
    live under an `agents/`-shaped dir) AND are not referenced by anything under
    an `evals/`-shaped tree.

The script self-roots via `git rev-parse --show-toplevel` (falls back to the
given --root / cwd outside a repo), is stdlib-only, supports --json, and exits
non-zero with an explained message on a hard failure. Every heuristic is a
*prior the LLM can override*, never a verdict — false positives here are cheap
because the skill grounds each one before scaffolding.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# --- tunables (documented, not magic) --------------------------------------

# Directory name fragments that mark an existing verification home. Matched
# case-insensitively against any path component.
TEST_DIR_HINTS = ("test", "tests", "spec", "__tests__")
EVAL_DIR_HINTS = ("eval", "evals", "evaluation", "evaluations", "benchmarks", "benchmark")

# Path components that mark generated / vendored / non-source trees: never
# counted as an "untested entrypoint" and never scanned for source.
SKIP_DIR_COMPONENTS = {
    "node_modules", "vendor", "third_party", "dist", "build", "out", "target",
    ".next", ".venv", "venv", "__pycache__", ".git", ".mypy_cache", ".pytest_cache",
    "migrations", "alembic", "__snapshots__", ".tox", "coverage", "htmlcov",
}

# Source extensions we reason about (kept small + mainstream on purpose).
SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rb", ".java", ".rs"}

# A file whose name matches one of these is itself a test (not a surface to test).
TEST_FILE_RX = re.compile(
    r"(^test_.+|.+_test\.[a-z]+$|.+\.test\.[a-z]+$|.+\.spec\.[a-z]+$|.+Test\.[a-z]+$|.+Spec\.[a-z]+$)"
)

# Signals that a file touches a non-deterministic (LLM/agent/prompt) surface.
# These are intentionally provider-agnostic — match the *shape*, not a vendor.
LLM_IMPORT_RX = re.compile(
    r"""(?ix)
    \b(
        anthropic | openai | langchain | llama_index | llamaindex | litellm |
        google\.generativeai | genai | mistralai | cohere | ollama |
        transformers | bedrock | vertexai | pydantic_ai | instructor |
        completion | chat\.completions | messages\.create | generate_content
    )\b
    """
)
# Prompt / agent / tool definition shapes (names, decorators, common keys).
LLM_SURFACE_RX = re.compile(
    r"""(?ix)
    ( system_prompt | \bprompt\b | \bagent\b | tool_call | tool_choice |
      function_call | @tool\b | def\s+tool | json_schema |
      response_format | temperature\s*= | max_tokens\s*= | lm_judge | llm_judge )
    """
)


class InventoryError(RuntimeError):
    """A fatal, explained error (printed to stderr; non-zero exit)."""


@dataclass
class Surface:
    path: str
    kind: str  # "deterministic" | "non_deterministic"
    reasons: list[str] = field(default_factory=list)


def run_git(args: list[str], cwd: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return out.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def resolve_root(root_arg: str | None) -> Path:
    start = Path(root_arg).resolve() if root_arg else Path.cwd()
    if not start.exists():
        raise InventoryError(f"--root path does not exist: {start}")
    top = run_git(["rev-parse", "--show-toplevel"], start)
    if top and top.strip():
        return Path(top.strip())
    # Not a git repo: degrade gracefully to the given/CWD root.
    return start


def _components(rel: Path) -> list[str]:
    return [p.lower() for p in rel.parts]


def _is_skipped(rel: Path) -> bool:
    return any(c in SKIP_DIR_COMPONENTS for c in _components(rel))


def _is_under_hint(rel: Path, hints: tuple[str, ...]) -> bool:
    return any(any(h == c or h in c for h in hints) for c in _components(rel))


def _is_test_file(rel: Path) -> bool:
    return bool(TEST_FILE_RX.match(rel.name)) or _is_under_hint(rel, TEST_DIR_HINTS)


def walk_sources(root: Path) -> list[Path]:
    """All candidate source files (relative paths), excluding skip/test/eval trees."""
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune skipped dirs in place for speed
        dirnames[:] = [
            d for d in dirnames
            if d.lower() not in SKIP_DIR_COMPONENTS and not d.startswith(".")
        ]
        rel_dir = Path(dirpath).relative_to(root)
        if _is_skipped(rel_dir):
            continue
        for fn in filenames:
            rel = rel_dir / fn if str(rel_dir) != "." else Path(fn)
            if rel.suffix.lower() in SOURCE_EXTS:
                out.append(rel)
    return out


def index_test_stems(files: list[Path]) -> set[str]:
    """Stems covered by an existing test file (the source name a test pairs with)."""
    stems: set[str] = set()
    for rel in files:
        if not _is_test_file(rel):
            continue
        name = rel.stem
        # peel common test markers to recover the source stem
        for pat in (r"^test_", r"_test$", r"\.test$", r"\.spec$", r"Test$", r"Spec$"):
            name = re.sub(pat, "", name)
        stems.add(name.lower())
    return stems


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, ValueError):
        return ""


def classify(root: Path, files: list[Path], test_stems: set[str],
             eval_refs: set[str]) -> tuple[list[Surface], list[Surface]]:
    """Split untested/un-evaled surfaces into deterministic and non-deterministic."""
    deterministic: list[Surface] = []
    non_deterministic: list[Surface] = []

    for rel in files:
        if _is_test_file(rel):
            continue
        if _is_under_hint(rel, EVAL_DIR_HINTS):
            continue  # eval harness code itself is not a surface-to-verify

        text = read_text(root / rel)
        is_llm = bool(LLM_IMPORT_RX.search(text)) or bool(LLM_SURFACE_RX.search(text))
        under_agents_dir = any(c in ("agents", "agent", "prompts", "chains", "graph")
                               for c in _components(rel))
        is_non_det = is_llm or under_agents_dir

        if is_non_det:
            if rel.stem.lower() in eval_refs or rel.name.lower() in eval_refs:
                continue  # something under evals/ references it -> treated as covered
            reasons = []
            if bool(LLM_IMPORT_RX.search(text)):
                reasons.append("imports/calls an LLM SDK")
            if bool(LLM_SURFACE_RX.search(text)):
                reasons.append("defines a prompt/agent/tool surface")
            if under_agents_dir:
                reasons.append("lives under an agent/prompt-shaped dir")
            non_deterministic.append(
                Surface(str(rel), "non_deterministic", reasons or ["LLM/agent surface"])
            )
        else:
            if rel.stem.lower() in test_stems:
                continue  # has a name-matching test -> treated as covered
            deterministic.append(
                Surface(str(rel), "deterministic", ["no name-matching test found"])
            )

    deterministic.sort(key=lambda s: s.path)
    non_deterministic.sort(key=lambda s: s.path)
    return deterministic, non_deterministic


def collect_eval_refs(root: Path, files: list[Path]) -> set[str]:
    """Module/path tokens referenced by files under an evals-shaped tree.

    A non-deterministic surface whose module is imported or whose path is named by
    the eval harness is treated as already covered (a PRIOR — the LLM still verifies
    the eval is non-vacuous). We match only **import targets and quoted module/path
    tokens**, never every bare identifier, so an incidental word in eval prose or a
    common module name mentioned in passing cannot silently suppress a genuinely
    unevaled surface from the inventory (a false negative is costlier here than a
    false positive: the dropped surface becomes invisible).
    """
    refs: set[str] = set()
    import_re = re.compile(r"(?m)^\s*(?:from|import)\s+([A-Za-z_][\w.]*)")
    quoted_re = re.compile(r"""["']([A-Za-z_][\w./-]{2,})["']""")
    for rel in files:
        if not _is_under_hint(rel, EVAL_DIR_HINTS):
            continue
        text = read_text(root / rel)
        for mod in import_re.findall(text):
            for part in mod.split("."):
                if len(part) >= 3:
                    refs.add(part.lower())
        for q in quoted_re.findall(text):
            for part in re.split(r"[\\/.]", q):
                if len(part) >= 3:
                    refs.add(part.lower())
    return refs


def find_dirs(root: Path, hints: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIR_COMPONENTS
                       and not d.startswith(".")]
        rel = Path(dirpath).relative_to(root)
        if str(rel) == ".":
            continue
        if any(h == rel.name.lower() or h in rel.name.lower() for h in hints):
            found.append(str(rel))
    return sorted(set(found))


def detect_run_hints(root: Path) -> list[str]:
    """Best-effort: how does this repo already run its checks? (precedence prior.)"""
    hints: list[str] = []
    pp = root / "pyproject.toml"
    if pp.exists():
        txt = read_text(pp)
        if "pytest" in txt:
            hints.append("pyproject.toml mentions pytest")
        if "[tool.poetry" in txt or "[project]" in txt:
            hints.append("python project (pyproject.toml)")
    pj = root / "package.json"
    if pj.exists():
        txt = read_text(pj)
        m = re.search(r'"test"\s*:\s*"([^"]+)"', txt)
        if m:
            hints.append(f'package.json test script: {m.group(1)}')
        if "vitest" in txt:
            hints.append("vitest present")
        if "jest" in txt:
            hints.append("jest present")
    if (root / "Makefile").exists():
        mk = read_text(root / "Makefile")
        for target in ("test", "eval", "evals", "check"):
            if re.search(rf"(?m)^{target}\s*:", mk):
                hints.append(f"Makefile target: {target}")
    wf = root / ".github" / "workflows"
    if wf.is_dir():
        hints.append(".github/workflows present (CI gate exists)")
    return hints


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Inventory verification coverage: what is tested/evaled vs not."
    )
    ap.add_argument("--root", default=None, help="Repo dir (default: enclosing git toplevel)")
    ap.add_argument("--top", type=int, default=40, help="Max surfaces to list per kind")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown")
    args = ap.parse_args(argv)

    try:
        root = resolve_root(args.root)
        files = walk_sources(root)
        if not files:
            raise InventoryError(
                "no source files found under root — check --root or the SOURCE_EXTS set"
            )
        test_stems = index_test_stems(files)
        eval_refs = collect_eval_refs(root, files)
        det, nondet = classify(root, files, test_stems, eval_refs)
        test_dirs = find_dirs(root, TEST_DIR_HINTS)
        eval_dirs = find_dirs(root, EVAL_DIR_HINTS)
        run_hints = detect_run_hints(root)
    except InventoryError as exc:
        print(f"eval_inventory: {exc}", file=sys.stderr)
        return 2

    total_src = sum(1 for f in files if not _is_test_file(f)
                    and not _is_under_hint(f, EVAL_DIR_HINTS))
    payload = {
        "root": str(root),
        "summary": {
            "source_files": total_src,
            "existing_test_dirs": test_dirs,
            "existing_eval_dirs": eval_dirs,
            "has_eval_home": bool(eval_dirs),
            "deterministic_unverified": len(det),
            "non_deterministic_unverified": len(nondet),
            "run_hints": run_hints,
        },
        "deterministic_unverified": [s.__dict__ for s in det[: args.top]],
        "non_deterministic_unverified": [s.__dict__ for s in nondet[: args.top]],
        "notes": [
            "Heuristics are PRIORS, not verdicts: ground each surface before scaffolding.",
            "An LLM/agent surface listed here may already be evaled indirectly — confirm.",
            "A deterministic file with no name-matching test may be covered by an "
            "integration test under another name — confirm before claiming a gap.",
        ],
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    s = payload["summary"]
    print("# Verification Inventory")
    print()
    print(f"Root: `{root}`")
    print(f"- Source files: {s['source_files']}")
    print(f"- Existing test dirs: {', '.join(f'`{d}`' for d in test_dirs) or '_none found_'}")
    print(f"- Existing eval dirs: {', '.join(f'`{d}`' for d in eval_dirs) or '_none found_ (no eval home)'}")
    print(f"- Run hints: {'; '.join(run_hints) or '_none detected — ask the user_'}")
    print()
    print(f"## Deterministic surfaces with no name-matching test ({len(det)})")
    print("_Verify with TESTS (input X -> output Y). Prior only — confirm before scaffolding._")
    print()
    for su in det[: args.top]:
        print(f"- `{su.path}` — {', '.join(su.reasons)}")
    if len(det) > args.top:
        print(f"- … +{len(det) - args.top} more")
    print()
    print(f"## Non-deterministic surfaces with no eval reference ({len(nondet)})")
    print("_Verify with EVALS (rubric / LM-judge over trajectory or generated output)._")
    print()
    for su in nondet[: args.top]:
        print(f"- `{su.path}` — {', '.join(su.reasons)}")
    if len(nondet) > args.top:
        print(f"- … +{len(nondet) - args.top} more")
    print()
    print("> Heuristics are priors, not verdicts. Ground each surface before scaffolding; "
          "a listed file may already be covered under another name.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
