#!/usr/bin/env python3
"""Routing eval — a deterministic regression guard for the skills' trigger surface.

The 5 code-quality skills (code-review, simplify, bug-swarm, churn-audit,
design-tradeoff) plus the 4 production-substrate skills overlap in vocabulary;
the ONLY thing separating them is each description's "Use when ..." specificity and
its "Do not trigger for ... (use <sibling>)" redirects. Those negative clauses are
untested prose — an edit that sharpens one "Use when" can silently start capturing
a sibling's prompts. This check encodes the intended routing for the known seams
and fails when a seam stops being disambiguated.

For each labelled case {prompt, expect, competitors}:
  - POSITIVE: the expected skill's "Use when" clause shares a trigger term with the
    prompt (it plausibly fires).
  - SEAM: for each competitor, the prompt is steered away from it by EITHER
      (a) a reciprocal redirect — expect named in the competitor's "Do not trigger",
          or the competitor named in expect's "Do not trigger"; OR
      (b) trigger specificity — the competitor's "Use when" shares no term with the
          prompt (it would not fire anyway).
    A seam with neither is a real ambiguity and fails.

Deterministic, stdlib-only, no LLM. A keyword heuristic is intentionally simple;
upgrade to an LM-judge later if it proves too coarse. Self-roots from evals/.
Reads cases.json next to this file. Supports --json. Exits non-zero on any failure.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SKILLS_DIR = REPO / "base" / "skills"

STOP = {
    "use","when","this","that","does","doing","done","with","without","into","onto",
    "the","and","for","not","you","your","our","its","are","was","were","has","have",
    "had","but","any","all","one","two","new","old","get","got","via","per","etc",
    "from","what","which","who","how","why","where","make","made","just","than","then",
    "before","after","over","under","about","across","whole","some","each","both","only",
    "skill","skills","repo","repos","code","codebase","project","projects","change",
    "changes","changed","file","files","work","working","review","reviewing",
}
WORD = re.compile(r"[a-z][a-z0-9-]{2,}")


def terms(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if w not in STOP}


def load_descriptions() -> dict[str, str]:
    """skill-name -> raw description string (from SKILL.md frontmatter)."""
    out: dict[str, str] = {}
    for d in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        md = d / "SKILL.md"
        if not md.is_file():
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^---\s*$(.*?)^---\s*$", text, re.S | re.M)
        fm = m.group(1) if m else text
        dm = re.search(r"description:\s*(.*)", fm, re.S)
        out[d.name] = (dm.group(1) if dm else "").replace("\n", " ")
    return out


def split_clauses(desc: str) -> tuple[str, str]:
    """(positive 'Use when' clause, negative 'Do not trigger' clause)."""
    low = desc.lower()
    neg_at = re.search(r"do not trigger|do not use|don'?t trigger|do not fire", low)
    pos_at = re.search(r"use when|use it when|use this when", low)
    neg = desc[neg_at.start():] if neg_at else ""
    if pos_at:
        pos_end = neg_at.start() if neg_at else len(desc)
        pos = desc[pos_at.start():pos_end]
    else:
        pos = desc[: neg_at.start()] if neg_at else desc
    return pos, neg


def main() -> None:
    ap = argparse.ArgumentParser(description="Routing regression eval for the skills' trigger surface.")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    ap.add_argument("--cases", default=str(HERE / "cases.json"), help="Path to cases.json")
    args = ap.parse_args()

    descs = load_descriptions()
    names = set(descs)
    pos_terms = {n: terms(split_clauses(d)[0]) for n, d in descs.items()}
    redirects = {
        n: {other for other in names if other != n and re.search(rf"\b{re.escape(other)}\b", split_clauses(d)[1])}
        for n, d in descs.items()
    }

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    failures: list[str] = []
    checked = 0

    for c in cases:
        prompt, expect, competitors = c["prompt"], c["expect"], c.get("competitors", [])
        checked += 1
        if expect not in names:
            failures.append(f"[{prompt!r}] expected skill '{expect}' does not exist")
            continue
        pt = terms(prompt)
        if not (pt & pos_terms[expect]):
            failures.append(f"[{prompt!r}] expected '{expect}' shares no trigger term with the prompt")
        for comp in competitors:
            if comp not in names:
                failures.append(f"[{prompt!r}] competitor '{comp}' does not exist")
                continue
            reciprocal = expect in redirects.get(comp, set()) or comp in redirects.get(expect, set())
            comp_would_fire = bool(pt & pos_terms[comp])
            if not reciprocal and comp_would_fire:
                failures.append(
                    f"[{prompt!r}] seam '{expect}' vs '{comp}' is undisambiguated: "
                    f"no redirect either way AND '{comp}' also matches the prompt"
                )

    ok = not failures
    if args.json:
        print(json.dumps({"ok": ok, "cases": checked, "failures": failures, "failure_count": len(failures)}, indent=2))
    else:
        for f in failures:
            print(f"FAIL {f}")
        print()
        print(f"{checked} routing cases checked — {'ALL PASS' if ok else str(len(failures)) + ' failure(s)'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
