# Contributing a skill

This repo's value is **contract discipline**, not volume. A new skill earns its place
only if it matches the bar of the existing ones. Before opening a PR, your change must
pass both evals (below) — they are the same gate that keeps the library from decaying.

```bash
python3 evals/validate_skills.py    # structural contract (frontmatter, refs, base:ids, scripts)
python3 evals/routing/check.py      # trigger-collision regression (add a case for a new skill)
```

## Scaffold a new skill

```bash
cp -r templates/skill-skeleton "base/skills/<your-skill>"
# then fill in SKILL.md, references/, (optional) scripts/, agents/openai.yaml
```

## A skill's anatomy

```
base/skills/<name>/
  SKILL.md                 # entrypoint: frontmatter + workflow body (< 500 lines)
  references/checklist.md   # DEFINES the stable base:<id> checks (required)
  references/*.md           # depth — loaded "only when you need it"
  scripts/*.py              # optional deterministic helpers (stdlib-only, --json)
  agents/openai.yaml        # interface + policy block
```

## The rules the evals enforce

1. **`description` is a 3-part routing contract.** It must say *what it produces*, a
   positive **"Use when ..."** clause, and a negative **"Do not trigger for: ... (use
   `<sibling>`)"** clause that redirects to the skills it could collide with.

   - ✅ `Best-in-class review of the current diff ... Use when asked to review a diff,
     a PR, staged changes ... Do not trigger for writing new code, non-review refactors
     (use simplify), or general Q&A.`
   - ❌ `Reviews code and finds problems.` (no triggers, no boundaries — it will
     mis-fire against `simplify`, `bug-swarm`, and `churn-audit`.)

   When you add a skill that overlaps an existing one, add the **reciprocal** redirect to
   *both* descriptions, and add a routing case to `evals/routing/cases.json`.

2. **Stable `base:<id>` ids.** Every check a profile can `OVERRIDE`/`SUPPRESS` gets a
   kebab id, **defined in `references/checklist.md`**. Every `base:<id>` you cite in
   `SKILL.md` must be defined there (the validator fails on a phantom id). Never renumber
   existing ids — they are the contract surface downstream profiles bind to.

3. **Body < 500 lines.** Push depth into `references/`; the body links to them with
   "only load what you need". Long deliverables are written to a file, not dumped inline
   (output-token discipline).

4. **Scripts are stdlib-only**, self-root via `git rev-parse --show-toplevel`, accept
   `--json`, exit non-zero on hard failure, and are invoked as `python3 <path>/x.py`
   (no executable bit assumed). Don't ship a hollow script — omit it if it adds nothing.

5. **Project-agnostic, always.** A base skill is *pure process*; everything
   project-specific is **data read at runtime** (the skill discovers `AGENTS.md` /
   `CLAUDE.md`, lint/test/CI config, and an optional `.agents/profiles/<name>.md`).
   **Never** hardcode a stack, and **never** commit proprietary or company-specific
   detail — this repo is public and must stay safe to replicate everywhere.

6. **Every skill carries the standard scaffolding:** a Step 0 context-absorption
   prelude, a single-pass-by-default / opt-in budget-gated fan-out posture, a
   human-approval pause before any write or spend, and a final self-check gate that
   verifies its own guardrails. Mirror `bug-swarm` or `code-review`.

A base change reaches every consuming project on its next pull — so a change here must be
safe for *every* project, not just yours.
