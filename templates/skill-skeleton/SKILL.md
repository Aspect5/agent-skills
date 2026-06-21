---
name: <skill-name>
description: >-
  <What it produces, in one clause.> Use when <concrete triggers — the phrasings a
  user would actually type>. Do not trigger for: <the adjacent jobs> (use
  <sibling-skill>); <another> (use <sibling-skill>); or general Q&A.
---

# <Skill Title>

<One-paragraph overview stating the hard contract this skill upholds.>

## Step 0 — Context-Absorption Prelude

Run this before anything else. Never fail for lack of a profile.

1. **Notice what's already in context.** `AGENTS.md` / `CLAUDE.md` (root and nested)
   are typically already loaded — use them; do not re-read needlessly.
2. **Read the profile if present:** `.agents/profiles/<skill-name>.md`. Apply its
   frontmatter knobs (`model`, `budget`, `fan_out`, `focus_paths`, `ignore_paths`) and
   its `## ADD` / `## OVERRIDE base:<id>` / `## SUPPRESS base:<id>` directives against
   `references/checklist.md`.
3. **Resolve commands** in precedence: profile → introspect the repo
   (`package.json` / `pyproject.toml` / `Makefile` / `.github/workflows`) → ask the user
   once → default. Never invent a command.
4. **Fall back to defaults** when no profile exists — the skill runs unmodified with zero
   config and better with one.

## Workflow

1. **<Step>.** <Deterministic where possible; cite scripts as
   `python3 "<path-to-skill>/scripts/x.py" --json`.>
2. **<Step>.** ...

## Budget & fan-out posture

Single-pass, single-agent is the default. Any multi-agent fan-out is **opt-in** behind a
cost preflight that honors `fan_out` (`never` | `ask` | `allowed`), `budget`, and `model`.

## Human-approval pause

Pause for explicit approval before any write / destructive / spend step. This skill never
mutates silently.

## Output discipline

Write the heavy deliverable to a file incrementally; emit only a tight summary inline.

## Guardrails

- <Hard rule the skill must never violate.>

## Self-check / quality gate

Before returning, verify every box — report literal results, never assert:

- [ ] <Every guardrail above is satisfied.>
- [ ] <Every `base:<id>` used is honored (minus any the profile SUPPRESSes).>

## References

Only load the reference files you need:

- `references/checklist.md` — the stable `base:<id>` checks profiles OVERRIDE/SUPPRESS.
