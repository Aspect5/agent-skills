#!/usr/bin/env python3
"""Structural validator for the agent-skills base library — the machine gate that
keeps the repo's contract discipline from decaying one merge at a time.

For every base/skills/<name>/ it asserts the conventions the repo promises:
  1. SKILL.md exists with parseable frontmatter; `name` is non-empty and equals
     the directory; `description` is non-empty.
  2. `description` is a 3-part routing contract: it has a positive "Use when ..."
     clause AND a negative "Do not trigger / use <x> instead" clause.
  3. SKILL.md is under MAX_BODY_LINES (depth belongs in references/).
  4. Every `references/<file>` mentioned in SKILL.md exists on disk.
  5. Every `base:<id>` referenced in SKILL.md is DEFINED in that skill's
     references/ (catches a profile OVERRIDE/SUPPRESS pointing at a phantom id).
  6. Each scripts/*.py compiles and accepts --json.
  7. agents/openai.yaml exists with an interface + policy block.
Plus a repo-level check: every `base:<id>` cited in docs/TAILORING.md and
profiles-template/*.md resolves to an id defined by some skill.

Stdlib only — no third-party deps, so it runs anywhere the skills do. Self-roots
from its own location (evals/ at the repo root). Supports --json. Exits non-zero
if any error is found.

Usage:
  python3 evals/validate_skills.py            # human report
  python3 evals/validate_skills.py --json     # machine report
"""

from __future__ import annotations

import argparse
import json
import py_compile
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO / "base" / "skills"
MAX_BODY_LINES = 500

BASE_ID = re.compile(r"base:[a-z0-9][a-z0-9-]*")
# A references/<file> mention inside SKILL.md (markdown link or inline code/path).
REF_MENTION = re.compile(r"references/([A-Za-z0-9_.-]+\.md)")


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return ({name, description}, body). Minimal YAML: handles a scalar `name:`
    and a `description:` that is inline OR a `>`/`|` block scalar. Stdlib only."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1 :])
    fields: dict[str, str] = {}
    i = 0
    key_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(.*)$")
    while i < len(fm_lines):
        m = key_re.match(fm_lines[i])
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest and rest[0] in "|>":
            # Block scalar: gather subsequent more-indented lines.
            block: list[str] = []
            i += 1
            while i < len(fm_lines) and (fm_lines[i].strip() == "" or fm_lines[i][:1] in " \t"):
                block.append(fm_lines[i].strip())
                i += 1
            fields[key] = " ".join(b for b in block if b).strip()
            continue
        # Inline scalar, possibly continued on following indented lines.
        val = rest.strip().strip("'\"")
        i += 1
        cont: list[str] = []
        while i < len(fm_lines) and fm_lines[i][:1] in " \t" and not key_re.match(fm_lines[i].strip()):
            cont.append(fm_lines[i].strip())
            i += 1
        if cont:
            val = (val + " " + " ".join(cont)).strip()
        fields[key] = val
    return fields, body


def has_positive_clause(desc: str) -> bool:
    return bool(re.search(r"use when|use it when|use this when", desc, re.I))


def has_negative_clause(desc: str) -> bool:
    return bool(
        re.search(
            r"do not trigger|don'?t trigger|do not use|not for\b|\(use [a-z0-9-]+\)|use [a-z0-9-]+ instead",
            desc,
            re.I,
        )
    )


def validate_skill(skill_dir: Path) -> list[str]:
    errs: list[str] = []
    name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"{name}: missing SKILL.md"]

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fields, _body = split_frontmatter(text)
    total_lines = len(text.splitlines())

    # 1. frontmatter
    if fields.get("name", "") != name:
        errs.append(f"{name}: frontmatter name ({fields.get('name')!r}) != directory name")
    desc = fields.get("description", "")
    if not desc:
        errs.append(f"{name}: empty or unparseable description")
    else:
        # 2. 3-part contract
        if not has_positive_clause(desc):
            errs.append(f"{name}: description missing a 'Use when ...' positive-trigger clause")
        if not has_negative_clause(desc):
            errs.append(f"{name}: description missing a 'Do not trigger / use <x> instead' negative clause")

    # 3. body length
    if total_lines >= MAX_BODY_LINES:
        errs.append(f"{name}: SKILL.md is {total_lines} lines (>= {MAX_BODY_LINES}); push depth into references/")

    # 4. referenced reference files exist
    for ref in sorted(set(REF_MENTION.findall(text))):
        if not (skill_dir / "references" / ref).is_file():
            errs.append(f"{name}: SKILL.md references references/{ref} which does not exist")

    # 5. base:<id> referenced in SKILL.md are defined in references/
    ref_text = ""
    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        for rf in refs_dir.glob("*.md"):
            ref_text += rf.read_text(encoding="utf-8", errors="replace") + "\n"
    defined = set(BASE_ID.findall(ref_text))
    referenced = set(BASE_ID.findall(text))
    for missing in sorted(referenced - defined):
        errs.append(f"{name}: SKILL.md uses {missing} but no references/*.md defines it")

    # 6. scripts compile + accept --json
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        for script in sorted(scripts_dir.glob("*.py")):
            try:
                py_compile.compile(str(script), doraise=True)
            except py_compile.PyCompileError as e:
                errs.append(f"{name}: scripts/{script.name} fails to compile: {e.msg.splitlines()[-1] if e.msg else e}")
            if "--json" not in script.read_text(encoding="utf-8", errors="replace"):
                errs.append(f"{name}: scripts/{script.name} does not accept --json")

    # 7. agents/openai.yaml structural sanity
    oy = skill_dir / "agents" / "openai.yaml"
    if not oy.is_file():
        errs.append(f"{name}: missing agents/openai.yaml")
    else:
        oy_text = oy.read_text(encoding="utf-8", errors="replace")
        for key in ("interface:", "policy:", "allow_implicit_invocation:"):
            if key not in oy_text:
                errs.append(f"{name}: agents/openai.yaml missing '{key.rstrip(':')}' block")

    return errs


def collect_defined_ids() -> set[str]:
    ids: set[str] = set()
    for refs in SKILLS_DIR.glob("*/references/*.md"):
        ids |= set(BASE_ID.findall(refs.read_text(encoding="utf-8", errors="replace")))
    return ids


def validate_doc_ids() -> list[str]:
    """Every base:<id> cited in the tailoring docs/templates must resolve."""
    errs: list[str] = []
    defined = collect_defined_ids()
    docs = [REPO / "docs" / "TAILORING.md", *sorted((REPO / "profiles-template").glob("*.md"))]
    for doc in docs:
        if not doc.is_file():
            continue
        for cited in sorted(set(BASE_ID.findall(doc.read_text(encoding="utf-8", errors="replace")))):
            if cited not in defined:
                errs.append(f"{doc.relative_to(REPO)}: cites {cited} but no skill defines it")
    return errs


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate the agent-skills base library against repo conventions.")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    args = ap.parse_args()

    if not SKILLS_DIR.is_dir():
        sys.stderr.write(f"error: {SKILLS_DIR} not found\n")
        sys.exit(2)

    skills = sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir())
    per_skill: dict[str, list[str]] = {}
    for d in skills:
        per_skill[d.name] = validate_skill(d)
    doc_errs = validate_doc_ids()

    all_errs = [e for v in per_skill.values() for e in v] + doc_errs
    ok = not all_errs

    if args.json:
        print(json.dumps({
            "ok": ok,
            "skills_checked": [d.name for d in skills],
            "errors": all_errs,
            "error_count": len(all_errs),
        }, indent=2))
    else:
        for d in skills:
            errs = per_skill[d.name]
            mark = "PASS" if not errs else "FAIL"
            print(f"[{mark}] {d.name}")
            for e in errs:
                print(f"        - {e}")
        for e in doc_errs:
            print(f"[FAIL] {e}")
        print()
        print(f"{len(skills)} skills checked — {'ALL PASS' if ok else str(len(all_errs)) + ' error(s)'}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
