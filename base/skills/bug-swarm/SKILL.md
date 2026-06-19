---
name: bug-swarm
description: >-
  Repro-first automated bug repair: reproduce the bug with a failing test, fan out
  diverse root-cause hypotheses in isolated git worktrees, tournament-select the
  minimal correct diff (or abstain with a diagnosis), then open a PR. Use when a bug
  has resisted 2+ sequential debugging attempts, or when the failure mode is clear
  but the root cause is genuinely ambiguous across layers (UI / service / data /
  schema / concurrency). Do not trigger for trivial one-line or already-diagnosed
  fixes, feature work, refactors, general Q&A, or reviewing an existing diff (use
  code-review for that).
---

# Bug Swarm

Test-driven, bounded parallel bug repair. The failing test is the oracle; parallel
agents propose *diverse* root causes; a tournament picks the minimal correct diff —
and if nothing survives verification, you **abstain with a diagnosis** rather than
ship a plausible-but-wrong patch. A confident no-fix beats a wrong fix.

## Overview

This is a tournament, not a linear investigation. You (1) reproduce the bug as a
**failing test** that the whole swarm shares, (2) fan out N hypotheses across the
stack in isolated worktrees, (3) hold every candidate to an **overfit guard** so a
patch can't special-case the repro, (4) select the smallest correct diff, and (5)
ship a PR or hand back a structured diagnosis. The fan-out is the expensive part and
is **budget-gated**: default is a single-pass repair, and multi-agent fan-out only
runs after an explicit cost preflight.

> Output discipline: write the full diagnosis / hypothesis log to a file
> (`bug-swarm-<slug>.md`) and emit only a tight summary inline. Never paste long
> traces or full diffs into the conversation.

## Step 0 — Context-Absorption Prelude

Run this before anything else. Never fail for lack of a profile.

1. **Notice what's already in context.** `AGENTS.md` / `CLAUDE.md` (root and nested,
   path-scoped) are typically already loaded — use them; do not re-read needlessly.
2. **Read the profile if present:** `.agents/profiles/bug-swarm.md`. If it exists,
   apply its frontmatter knobs (`model`, `budget`, `fan_out`, `focus_paths`,
   `ignore_paths`) and its `ADD` / `OVERRIDE base:<id>` / `SUPPRESS base:<id>`
   directives against the checklist in `references/checklist.md`.
3. **Resolve commands** in this precedence, first hit wins:
   profile `commands` → `$BUG_SWARM_TEST_CMD` → introspect the repo
   (`package.json` / `pyproject.toml` / `Makefile` / CI workflows) → ecosystem
   default. Use the helper:
   `python3 "<path-to-skill>/scripts/detect_test_cmd.py" --json`. If it returns
   `source: none`, **ask the user once** for the test command; do not guess.
4. **Fall back to defaults** when no profile and no override exist — the skill must
   run unmodified with zero config.

Honor the budget posture from the start: `fan_out: never` ⇒ stay single-pass;
`fan_out: ask` ⇒ run the cost preflight before Step 4; `model: gpt-5.4` ⇒ prefer
lower-freedom, script-anchored steps over open-ended prose.

## Workflow

### 1. Frame and gate the trigger

- Restate the bug in one line: **user-visible symptom + expected behavior**.
- Confirm this is in scope: it resisted ≥2 sequential attempts OR the root cause is
  genuinely ambiguous across layers. If it's a one-line/already-diagnosed fix, say so
  and decline the swarm — just fix it directly.
- Gather evidence into ≤5 bullets (known vs unknown). Pull any trace/log the user
  provides; sample implicated data read-only. If the failure mode still isn't
  concrete enough to write an assertion, **stop and ask** — do not start a swarm on a
  vague symptom.

### 2. Reproduce first — the hard gate

- Write the **smallest** test that reproduces the bug, asserting on user-visible
  behavior, not an internal detail. Place it where the project's tests live (mirror an
  existing test's framework/async pattern).
- Run it with the resolved test command. **It must FAIL on HEAD, for the expected
  reason** (the bug — not an import error, fixture typo, or setup mistake).
- A test that is **green on HEAD is rejected**: it does not capture the bug. Iterate
  until red-for-the-right-reason. This gate is non-negotiable — without a failing
  oracle the swarm drifts.
- Create the working branch off the base branch (resolved from git; never assume
  `main`) and commit the repro:

  ```bash
  base="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@')"
  base="${base:-$(git rev-parse --abbrev-ref HEAD)}"
  git fetch origin
  git switch -c "bug-swarm/<slug>" "origin/${base}"
  # ...write the repro test, confirm RED...
  git add <test-file> && git commit -F - <<'MSG'
  test(<scope>): failing repro for <bug>
  MSG
  ```

### 3. Localize (prior, not constraint)

Narrow where the fix likely lives — as a *prior* the hypotheses can override, never a
fence:

- `git blame` / `git log -p` on the trace's frames and the asserting lines.
- `git log -S'<symbol>'` pickaxe for where a value/contract last changed.
- Change-coupling neighbors (files that co-change with the suspect) and import
  proximity.

Record the localization in the diagnosis file. Do not let it collapse the hypothesis
diversity in the next step.

### 4. Fan out DIVERSE hypotheses (budget-gated)

This is the opt-in, cost-bearing step. **Run a cost preflight first:**

> "This will dispatch N=<n> parallel fix agents (~<n> subagents). Proceed? (honoring
> `fan_out: <value>` and `budget`)."

- `fan_out: never` ⇒ skip fan-out; do a single careful sequential repair instead, then
  go to Step 5 with that one candidate.
- `fan_out: ask` ⇒ get explicit approval before dispatching.
- `fan_out: allowed` ⇒ proceed; still cap N at the profile/budget ceiling.

Pick **distinct root-cause families** (see `references/hypothesis-families.md`) — not
N samples of the same patch. A good default spread:

- **Input/edge** — null/empty/boundary input, off-by-one, missing default.
- **State/ordering/concurrency** — race, stale cache, mutation order, re-entrancy.
- **Contract/schema mismatch** — producer↔consumer drift, type/serialization, both
  sides of the boundary.

For each hypothesis, create an isolated worktree off the repro branch — **never edit
the user's working tree**:

```bash
git worktree add ".bug-swarm/<slug>-h1" "bug-swarm/<slug>"
git worktree add ".bug-swarm/<slug>-h2" "bug-swarm/<slug>"
git worktree add ".bug-swarm/<slug>-h3" "bug-swarm/<slug>"
```

Dispatch one agent per worktree, in a single message for true parallelism (use the
profile's `model`; default to the strongest available). Each agent gets: the bug
summary + evidence, the repro test path, its assigned hypothesis + a **scope
constraint** (e.g. "only edit `frontend/**`"), and the **termination condition**:
repro test passes AND the full suite stays green AND no new lint/type errors. Agents
must stay inside scope — out-of-scope edits are an automatic disqualifier.

### 5. Overfit guard — mandatory

A patch that only makes the repro pass is not a fix. For each candidate, before it can
win (full rubric in `references/overfit-guards.md`):

- Run the **full regression suite** — any newly broken test disqualifies.
- Run **1–2 adversarial sibling tests** the patch never saw (same bug class, different
  inputs). The patch must pass these too.
- **Reject** patches that special-case the repro's literal inputs, weaken/loosen
  existing assertions, broaden a `try/except`, comment out a check, or mark tests
  skip/xfail to go green.

### 6. Tournament select — or ABSTAIN

Among candidates that survive Step 5, rank by:

1. **Correctness** — repro + siblings + full suite green (gate; non-negotiable).
2. **Minimal blast radius** — smallest diff, fewest files, no public-contract change.
3. **Cleanliness** — no new lint/type errors, no new dead code.
4. **Root-cause clarity** — tie-break on the clearest, most general diagnosis (an
   LLM-judge fix-spec check catches consensus-overfit where every agent special-cased
   the same way).

**If nothing survives Step 5**, do **not** ship the least-bad patch. Abstain: return
the committed repro test + the ranked hypotheses + why each failed + a proposed next
move (different hypothesis set, deeper instrumentation), and mark **needs-human**.

### 7. Ship (human-approval pause) or hand back

- **Pause for approval** before any push / PR / branch publish — this is the
  outward/irreversible step.
- Winner path: from the winning worktree, run the project's own quality gate (Step 8),
  push the branch, and open a PR with `gh` if authed (else emit the branch name +
  `git format-patch` output and the exact push/PR commands). PR body:
  `## Summary` · `## Root cause` · `## Test plan` (new repro + sibling tests + the
  literal gate pass line) · `## Alternatives considered` (one line per rejected
  hypothesis and why) · `## Evidence` (trace/log link). Title in Conventional Commits:
  `fix(<scope>): <symptom>`.
- Abstain path: open a **draft diagnosis-only PR** carrying the repro test + the
  hypothesis writeup, so the bug never becomes invisible again.
- Clean up the losing worktrees (`git worktree remove`); keep the winner until merge.

### 8. Self-check / quality gate (final word)

Before declaring done, verify every box — report the literal results, do not assert:

- [ ] Repro test **failed on HEAD** for the right reason and **passes** on the fix.
- [ ] The bug-fix test is a real regression test: it fails on the buggy code and
      passes on the fixed code (not vacuous coverage).
- [ ] Full suite + adversarial siblings are green on the winner.
- [ ] No assertion was weakened, no check removed, no test skipped to go green.
- [ ] The winning diff is scope-local and touches no migration / schema / auth
      contract without explicit escalation (guardrail below).
- [ ] The project's own quality gate ran and **passed** — paste its literal pass line
      (capture its own exit code; never pipe to `tail`/`head`, which masks it).
- [ ] All worktrees except the winner are removed; the user's working tree is
      untouched.
- [ ] Full diagnosis is in `bug-swarm-<slug>.md`; only a summary went inline.

If any box fails, fix it or fall to the abstain path. Do not ship on a partial gate.

## Guardrails

- **Scope-local only.** Never autonomously change migrations, DB schema, auth/security
  contracts, or public API shapes to make a test pass — escalate to a human instead.
- **Never commit to a protected branch** (`main`/`staging`/`master`). PR only.
- **The repro test is mandatory.** No failing oracle ⇒ no swarm.
- **Don't touch the user's working tree** — all edits happen in worktrees.
- **Shell-safety:** single-quote or heredoc commit messages (backticks run command
  substitution on zsh); check exit codes directly; never pipe a gate to `tail`/`head`.
- Respect a per-agent time budget; if exceeded, stop and report (abstain path).

## References

Load only the reference files you need:

- `references/checklist.md` — the stable `base:<id>` checks profiles can
  OVERRIDE/SUPPRESS.
- `references/hypothesis-families.md` — the diverse root-cause families to spread N
  across, with the signal that suggests each.
- `references/overfit-guards.md` — the full reject/accept rubric for the overfit guard
  and the adversarial sibling-test recipe.
- `references/pr-templates.md` — PR body + draft diagnosis-PR templates.
