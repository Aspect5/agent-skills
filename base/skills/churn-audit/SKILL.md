---
name: churn-audit
description: >-
  Produces a churn-driven architecture advisory: ranks unstable/hotspot files
  by relative churn × complexity, surfaces cross-boundary change coupling and
  ownership/bus-factor risk, and recommends boundary fixes tied to evidence.
  Use when asked to audit hot spots, high-churn or repeatedly-edited files,
  recent commit/PR activity, unstable areas, architectural risk, refactor
  priorities, or "where is the codebase fighting itself". Advisory by default —
  it diagnoses and recommends, it does not refactor.
  Do not trigger for: reviewing a specific diff/PR before merge (use code-review),
  general dead-code/de-slop cleanup, implementing an already-decided refactor,
  bug reproduction, or non-git-history questions.
---

# Churn Audit

## Overview

Use commit churn as a **signal, not a verdict**. The job is to find recently
unstable files and flows, understand *why* they keep changing, and produce
architectural advice that lowers future change cost. High churn is a prompt to
investigate — it is never proof of bad design (active feature work, planned
migrations, and generated code all churn legitimately). Every claim is anchored
in evidence (relative churn, complexity, coupling, ownership, PR/incident
context, project docs). Default output is an **advisory report written to a
file**, with a tight summary inline. Edit code only if the user explicitly asks
for implementation, or for a tiny safe doc/comment fix.

> Only load the reference files you need. Heavy detail lives in `references/`:
> [`signals.md`](references/signals.md) (how each metric is computed + read),
> [`diagnosis-checklist.md`](references/diagnosis-checklist.md) (the `base:<id>`
> failure-mode checklist profiles can OVERRIDE/SUPPRESS),
> [`report-template.md`](references/report-template.md) (the deliverable shape).

## Step 0 — Context-Absorption Prelude

Run this before any analysis. Never fail for lack of a profile — fall back to defaults.

1. **Repo guidance already in context.** `AGENTS.md` / `CLAUDE.md` are typically
   already loaded. Also read `ARCHITECTURE.md`, ADRs (`docs/adr`, `docs/decisions`),
   and `CONTRIBUTING` if present, so intentional architecture is not mislabeled
   as dysfunction. If repo docs require a branch-freshness check before audits,
   honor it (e.g. `git fetch && git log --oneline HEAD..origin/<default>`); a
   stale tree produces phantom findings.
2. **Profile.** If `.agents/profiles/churn-audit.md` exists, read it and apply:
   frontmatter knobs (`model`, `budget`, `fan_out`, `focus_paths`, `ignore_paths`,
   `window`, `boundaries`) and the body's `## ADD` / `## OVERRIDE base:<id>` /
   `## SUPPRESS base:<id>` directives against the checklist in
   [`references/diagnosis-checklist.md`](references/diagnosis-checklist.md).
3. **Resolve the window & boundaries.** Choose `--since` from the request shape
   (profile `window` → else: 14–30d for recent instability, 90d for architectural
   drift, 6–12mo for long-term hotspots). Infer module boundaries from
   directory/package layout; honor any profile `boundaries` / `CHURN_BOUNDARIES`
   override and pass them as `--boundary`.
4. **Defaults if nothing found.** 90-day window, depth-2 boundaries, advisory-only.

## Workflow

1. **Compute churn signals (deterministic, do not eyeball git log).** Run the
   bundled script — it self-roots via `git rev-parse --show-toplevel`, so it
   works from any subdirectory:

   ```bash
   python3 "<path-to-skill>/scripts/churn_report.py" --since "90 days ago" --window-days 90 --top 30
   ```

   - Match `--window-days` to `--since`. For a branch/PR range use
     `--base-range 'origin/main..HEAD'` instead of `--since`.
   - Pass profile/inferred boundaries with `--boundary <prefix>` (repeatable);
     add `--exclude '<regex>'` for project-specific generated paths. Generated
     code, lockfiles, vendored trees, snapshots, and migrations are excluded by
     default — keep them out of hotspot ranking unless they ARE the point.
   - Use `--json` when you want to post-process; otherwise read the Markdown.
   - Read [`references/signals.md`](references/signals.md) to interpret
     `hotspot_score`, `relative_churn`, `bus_factor`, and coupling `degree`
     correctly. Key idea: **rank by relative churn × complexity, not raw lines** —
     a small file rewritten many times outranks a huge file with equal absolute
     churn, and a complex hotspot costs far more than a simple one.

2. **Add PR / incident context where it explains the churn.** If `gh` is
   authenticated and the user asked for (or you need) GitHub history, use
   `gh pr list` and `gh pr view <n> --json title,body,files,reviews,labels,mergedAt,author`
   on the PRs touching top hotspots. Look for revert/fix-forward loops, repeated
   review comments on the same contract, and `bug`/`migration`/`refactor` labels.
   A one-time migration or generated churn should be **demoted**, not flagged.
   No network/`gh`? Say so and proceed on local history.

3. **Inspect each top hotspot.** For the top files/dirs, read recent patches
   (`git log -p -- <path>`, `git log -L :func:<path>` for repeated functions) and
   map the **change surface**: callers, consumers, tests, persisted schemas,
   event contracts, configs, background jobs. Cross-reference the coupling table:
   a cross-boundary co-change pair is a candidate leaky abstraction or duplicated
   source of truth.

4. **Diagnose the architecture (not the symptom).** For each hotspot, work the
   failure-mode checklist in
   [`references/diagnosis-checklist.md`](references/diagnosis-checklist.md)
   (unclear ownership, contract changes forcing coordinated edits, leaky/duplicate
   abstraction, tests coupled to implementation, missing schema boundary, state
   spread across stores, operational concerns tangled with domain logic). Then ask
   the **redo question**: "if we rebuilt this area now, what simpler boundary would
   we pick?" — and weigh that target against migration cost and current risk.
   Demote **complex-but-stable** code: high refactor risk, low payoff. Use the
   complexity *trend* over the window (rising = decaying; falling = healing).

5. **Separate healthy from unhealthy churn, and rank by future-change cost.**
   Explicitly list what to **leave alone** (churn explained by active feature
   work, planned rewrites, or generated code). Rank recommendations by the cost
   they remove, not by raw churn. Watch ownership: a hotspot with `bus_factor: 1`
   and a high minor-author fraction is an organizational risk even if the code is
   clean (org metrics out-predict code metrics).

6. **Write the advisory (output discipline).** Write the full report to a file
   (default `churn-advisory.md` in the repo root, or a profile/user-named path),
   incrementally, using [`references/report-template.md`](references/report-template.md):
   Executive Read → Hotspot table → per-area Deep Dives (evidence → current shape
   → failure mode → if-starting-over → first safe step) → Leave Alone → ordered
   Action Plan. For each recommendation name payoff, risk, migration path, and the
   first safe step. **Emit only a 5–8 line summary inline** (top 3 hotspots + the
   single best first move + the report path) — never paste the whole report.

7. **Self-check / quality gate (run before reporting).**
   - **Evidence**: every hotspot claim cites a concrete `file` + signal
     (commits, relative_churn, coupling pair, or PR). No "feels unstable".
   - **No false alarms**: each top finding survives the "is this healthy churn?"
     test (migration / generated / active-feature) — demote if it is.
   - **Boundary-relevant coupling only**: report coupling that crosses a module
     boundary; intra-boundary co-change (a file and its own test) is expected,
     not a smell. The script already drops exact-stem source/test pairs; manually
     **demote any remaining pair that is just a file and its own test** under a
     non-matching name (e.g. `schemas.py` ↔ `test_artifact_schemas.py`) before you
     report it as an architectural smell.
   - **Advisory, not cosmetic**: every recommendation changes a boundary,
     ownership, or contract — not formatting. No code was edited unless the user
     asked.
   - **Freshness**: confirm the tree is not stale vs the default branch (Step 0).

## Budget & fan-out posture

- **Default is a single-pass, single-agent audit** — the script does the heavy
  deterministic work, so one pass is usually sufficient and cheapest. Honor the
  profile `model` (`gpt-5.4` → lean harder on the script's numbers and lower
  prose freedom; `gpt-5.5` → more architectural-judgment latitude) and `budget`.
- **Multi-agent fan-out is opt-in only.** Use parallel subagents only when the
  user explicitly asks for agents/delegation/parallel work, the codebase is large
  enough to warrant it, and the profile permits it (`fan_out: allowed`; if
  `fan_out: ask`, do a **cost preflight** first — "this is ~N subagents across
  forensics / architecture-reader / contract-audit / test-incident lens, proceed?"
  — and wait for approval; if `fan_out: never`, stay single-pass). Each subagent
  returns evidence only and edits nothing. Suggested independent tracks: Churn
  Forensics, Architecture Reader, Contract Audit, Test/Incident Lens.

## Human-approval pause

This skill is advisory and read-only by default. If the user asks you to act on a
recommendation (refactor, move a boundary, delete code), **stop and confirm the
specific change first**, then hand off to the appropriate implementation/skill —
do not perform a write or destructive step inside this audit without explicit
approval.
