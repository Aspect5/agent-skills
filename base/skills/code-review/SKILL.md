---
name: code-review
description: Best-in-class, high-signal review of the current diff/PR on ANY repo, learning the repo's conventions from the repo itself. Produces a severity-ranked report (blockers / should-fix / nits) where every finding carries a file:line proof and survives adversarial self-verification, biased toward approval. Use when asked to review a diff, a PR, a branch, staged changes, or "the changes before merge"; when asked "is this safe to merge", "find bugs in this diff", or "review my PR". Do not trigger for writing new code, implementing a feature, non-review refactors (use simplify), security threat-modeling of a whole system, or general Q&A about the codebase.
---

# Code Review

## Overview

Review the changes in the current diff — not the whole repo, but the changed lines — and return a tight, ranked, low-false-positive report. The discipline that makes this best-in-class: (1) **learn the repo's conventions before judging** so you never re-flag what CI already enforces; (2) **compute reviewer dimensions from `changed files × project profile`** instead of running a fixed checklist; (3) **ground every finding in resolved context** (callers, callees, types, tests) because missing related files is the #1 false-positive cause; (4) **adversarially try to refute each finding** before it ships; (5) **bias toward approval** — a noisy review is worse than a short one.

The whole repository is context for *judging*. Only **changed lines** are eligible to be *flagged* (pre-existing issues go in a muted tier).

## Step 0 — Context-Absorption Prelude

Before any analysis, absorb context so the rest of the workflow runs against this repo's reality, not generic assumptions:

1. **Notice what's already in context.** `AGENTS.md` / `CLAUDE.md` (root and nested) are typically already loaded — re-read the parts relevant to review conventions, risky paths, and quality gates rather than re-fetching.
2. **Read the profile if present.** Look for `.agents/profiles/code-review.md`. If it exists, apply its frontmatter knobs (`commands`, `severity_floor`, `focus_paths`, `ignore_paths`, `model`, `budget`, `fan_out`) and its `## ADD` / `## OVERRIDE base:<id>` / `## SUPPRESS base:<id>` sections against the base checklist in `references/checklist.md`. A SUPPRESSed `base:<id>` is never flagged; an OVERRIDDEN one uses the project's rebinding.
3. **Resolve commands** in this precedence: profile `commands` → introspect `package.json` / `pyproject.toml` / `Makefile` / `*.cfg` / CI config (`.github/workflows`, `cloudbuild*.yaml`, `.gitlab-ci.yml`) → ask the user once if still ambiguous. Never invent a command.
4. **Fall back to defaults** when no profile exists. The skill must run usefully with zero config — never fail or stall for lack of a profile.

## Workflow

### 1. Scope the diff (deterministic, not by eyeball)

Resolve the review range, then run the scoping script — it self-roots via `git rev-parse`, so it works from any subdirectory:

```bash
# Whole working tree (staged + unstaged) vs HEAD — default for "review my changes":
python3 "<path-to-skill>/scripts/scope_diff.py" --json
# A PR / branch range (preferred when reviewing a PR — merge-base semantics):
python3 "<path-to-skill>/scripts/scope_diff.py" --base "<base-ref>" --head "<head-ref>" --json
```

For a PR by number, fetch metadata + range with `gh` if available (`gh pr view <N> --json baseRefName,headRefName,title,body,files,isDraft`); otherwise ask for the base/head refs. **Confirm the base branch matches the project's convention** (read it from `AGENTS.md`/`CLAUDE.md`/profile — do not assume `main`); if a PR targets an unexpected base, flag that as a process issue before the content review.

The script returns per-file `category`, `review_relevant`, `risky_hits`, and a `suggested_tier`. Lockfiles / vendored / generated / binary are listed but marked low-signal — do not read their patches line-by-line; migrations are always kept and high-priority. Re-add `--patch` to pull per-file patch text once you know which files matter.

### 2. Build the ProjectProfile (convention discovery)

Resolve conventions in this precedence (**last wins**) and write down a short ProjectProfile you'll hand to every reviewer dimension:

`REVIEW.md` (or `.github/REVIEW.md`) → `AGENTS.md` / `CLAUDE.md` (incl. nested, path-scoped) → `CONTRIBUTING*` / `docs` style guides → lint / format / type / test / CI config → inferred-from-code conventions.

The ProjectProfile records: languages & frameworks, architectural layers, the migration tool, the security surface, **what CI already enforces** (→ a hard skip list: never re-flag lint, format, import order, or type errors the toolchain already catches), team-accepted exceptions, and any severity recalibration the project asks for. See `references/reviewer-dimensions.md` for how this drives dispatch.

### 3. Risk-tiered dispatch (reviewers are COMPUTED, never a fixed list)

Pick a tier from the scope summary, then compute which review *dimensions* fire from `changed_files × ProjectProfile`. **Do not run a hardcoded reviewer set.**

- **Trivial** (`suggested_tier: trivial`, ≤10 changed lines, no risky path): correctness only, single pass, lean.
- **Standard** (`suggested_tier: standard`, ≤100 lines, no risky path): correctness + the 2–3 dimensions whose trigger predicates match.
- **Full** (`suggested_tier: full`: >100 lines, ≥50 files, or any risky-path hit): every dimension whose predicate matches.

Dimension menu — each fires **only if its predicate matches** (full predicates + `base:<id>` mapping in `references/reviewer-dimensions.md`):

- **correctness** — always.
- **security** — source / auth / migration / CI-build / secret-shaped files touched.
- **api-contract** — a public/exported signature, route, event, or schema changes → audit BOTH producer and consumer.
- **data-migrations** — a migration / schema file is touched.
- **performance** — hot-path, loop-over-IO, N+1, or large-data code touched.
- **tests** — source or test files touched (does a new test fail-on-bug / pass-on-fix?).
- **design-system** — frontend code touched **and** a style/design doc exists in the repo.
- **docs-consistency** — docs/config-only changes (verify every path/symbol/URL claim).
- **platform-portability** — CI scripts, shell, Dockerfiles, or build config touched.

**Catch-all:** if no predicate matches any changed file, run correctness + security and flag the PR for human classification — never produce a zero-dimension (silent empty) review.

**Single-pass is the default.** Merge the matched dimensions into ONE review pass. Multi-agent fan-out (one subagent per dimension + an independent verifier) is **opt-in** and **budget-gated** — see Step 8.

### 4. Ground each dimension (the #1 false-positive defense)

For every changed region a dimension cares about, resolve its context before judging: the **callees** it invokes, the **callers** that reach it, the **type/init/config sites** of the values it touches, and the **tests** that exercise it. A finding raised without its related files is the single largest source of false positives — if you can't see how a value is constructed or consumed, you can't assert it's wrong. Pre-existing bugs you notice while grounding go in a separate **muted** tier; do not block the diff on them.

### 5. Apply the checklist by dimension

Run the dimension checks in `references/checklist.md` (stable `base:<id>` ids; respect profile OVERRIDE/SUPPRESS). Each candidate finding must carry: a `file:line`, a one-line issue, a concrete impact, a minimal suggested fix, and a **confidence** (high / medium / low). No `file:line` proof ⇒ not a finding.

### 6. Adversarial self-verification (the false-positive floor)

Before a candidate becomes a reported finding, it must survive ALL of these (the full procedure is in `references/severity-rubric.md` → "FP-suppression gauntlet"):

1. **Prove-the-behavior** — re-open the cited code (and its callees/callers) or run a check; drop anything you can't prove with a concrete artifact.
2. **Already-handled** — is this guarded upstream/downstream, or by a validator/type the diff doesn't show? If yes, drop it.
3. **Convention / CI-skip** — does the ProjectProfile say CI already enforces this, or the team accepts it? If yes, drop it (never re-flag lint/format/types).
4. **What-not-to-flag** — no theoretical or defense-in-depth nags (e.g. "could be exploited if an attacker controlled X" where X is server-constant), no speculative refactors outside the diff, no style preference dressed as a bug.
5. **Re-review convergence** — on a re-run of an already-reviewed PR, suppress brand-new nits; only surface regressions and previously-missed blockers/should-fixes.

At **full** tier (or when fan-out is enabled), an independent verifier pass tries to **refute** each blocker and should-fix; a finding no one can refute survives, the rest are downgraded or dropped.

### 7. Severity, aggregation, and output

Assign severity per `references/severity-rubric.md`: 🔴 **blocker** / 🟠 **should-fix** / 🟡 **nit** (cap inline nits at ≤5; summarize the rest) / 🟣 **pre-existing** (muted). Dedup by `file:line + root-cause`, rank blockers → should-fix → nits, and **lead with a one-line tally + a merge verdict**, biased toward approval.

**Output discipline:** if the review is more than a short summary, write the full report to a file (`code-review-<scope>.md` in the repo root or a path the user names) incrementally, and emit only a tight inline summary (tally + verdict + the top blockers). Don't dump a multi-page review into the chat. End each dimension with a one-line **coverage note** — even "nothing found" must be stated, because silence ≠ checked.

### 8. Budget & fan-out posture (cost preflight before any multi-agent run)

Single-pass merged review is the default and needs no preflight. **Before any multi-agent fan-out** (per-dimension subagents and/or the independent verifier):

- Honor the profile `fan_out` knob: `never` → never fan out (single pass only); `ask` → state "this is ~N subagents (one per matched dimension + 1 verifier) — proceed?" and wait; `allowed` → proceed but still announce the count.
- Honor `budget` and `model`: on a cheaper model or a tight budget, prefer the lean single-pass path and lower-freedom scripted checks; on a more capable model with headroom, prose latitude and fan-out are fine.
- Fan out **only at standard/full tier** with multiple matched dimensions — never for a trivial diff.

### 9. Human-approval pause before any write

This skill **reports**; it does not mutate by default. Do not commit, push, post a PR comment, or apply a suggested patch unless the user explicitly asked for it (e.g. `--comment` to post via `gh pr comment`, or `--fix` to apply to the working tree). For any such action, pause for explicit approval first, use shell-safe command construction (single-quote / heredoc commit and comment bodies — never backtick-substitute on zsh), and after any `git push` verify the remote tip matches local HEAD before claiming success.

### 10. Self-check (quality gate before returning)

Confirm every item before handing back the review:

- [ ] Scope came from `scope_diff.py`; only **changed lines** are flagged; pre-existing issues are in the muted tier.
- [ ] A ProjectProfile was built; nothing CI already enforces was re-flagged.
- [ ] Reviewer dimensions were **computed** from `changed files × profile`, not a fixed list; the catch-all prevented a zero-dimension review.
- [ ] Every finding has a `file:line` proof, a confidence, and survived the FP-suppression gauntlet.
- [ ] Severity is assigned; nits are capped ≤5 inline; the report leads with a tally + verdict and is biased toward approval.
- [ ] Long reports were written to a file; only a tight summary is inline.
- [ ] No write/spend happened without explicit approval + a cost preflight for fan-out.

## References

Only load the reference files you need:

- `references/checklist.md` — the per-dimension check catalog with stable `base:<id>` ids (profiles OVERRIDE/SUPPRESS by id).
- `references/reviewer-dimensions.md` — trigger predicates that map `changed files × ProjectProfile` → which dimensions fire.
- `references/severity-rubric.md` — severity definitions, the FP-suppression gauntlet, per-dimension "what NOT to flag", and the report template.
