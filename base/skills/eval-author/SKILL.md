---
name: eval-author
description: >-
  Stands up or strengthens a repo's verification suite: inventories what behavior
  and agent surfaces lack verification, then scaffolds deterministic TESTS for
  deterministic logic (input X -> output Y) AND EVALS for non-deterministic parts
  (agent trajectory + generated-output quality) using labelled datasets, explicit
  anchored rubrics, and calibrated LM-judge checks — with a runnable evals/ layout,
  a pass/threshold-gated runner, and an honest coverage report. Use when asked to
  add or improve evals, set up an eval/verification harness, write scoring rubrics,
  regression-test a prompt/agent/LLM feature, measure generated-output quality, or
  answer "how do we know this AI feature actually works". Do not trigger for:
  reviewing a diff/PR (use code-review); reproducing and fixing one failing test
  (use bug-swarm); writing a spec or acceptance criteria that DEFINE what correct
  means (use spec-author — eval-author MEASURES against a spec, it does not author
  one); auditing the agent harness/tool-surface/guardrail config itself (use
  harness-audit); building a deterministic fail-closed hook/check that BLOCKS a
  danger surface — secrets, force-push, a "never do X" policy — rather than
  measuring quality (use guardrail-author); or general Q&A.
---

# Eval Author

Set the bar at the eval, not the demo. This skill stands up the verification a
repo is missing: it finds the surfaces with no oracle, then scaffolds **both**
kinds the New-SDLC framework keeps separate — **tests** for the deterministic
parts (same input → same output) and **evals** for the non-deterministic parts
(agent trajectory and generated-output quality), scored against labelled datasets,
explicit anchored rubrics, and calibrated LM-judge checks. The hard contract: it
writes runnable scaffolding and reports **honest** coverage (what is verified *and*
what is not) — it **does not invent passing results**.

## Overview

A feature is only "done" when its behavior is *verified*, and the two surfaces are
verified differently. Deterministic logic gets an exact test. The stochastic core —
the model's answer, the agent's plan — gets an eval: a labelled set, a written
rubric, a scored threshold. A suite with only one half is incomplete by
construction; a green score from an unlabelled, leaked, or always-passing eval is
worse than no eval because it manufactures false confidence. So every eval this
skill scaffolds must be able to **fail** — green on the right output, red on a
seeded bad one — and every coverage claim shows its denominator.

This skill **scaffolds and reports**; it does not fabricate scores and does not
fix the code under test. It hands off cleanly: gaps where "correct" was never
defined go to `spec-author`; risks in the agent's tool/guardrail config go to
`harness-audit`.

> Output discipline: write the heavy deliverable (the coverage report, the
> datasets, the rubrics) to files incrementally, and emit only a tight summary
> inline (tally + biggest gap + run command + path). Never paste a full matrix or
> dataset into the conversation.

## Step 0 — Context-Absorption Prelude

Run this before anything else. Never fail for lack of a profile — fall back to
defaults.

1. **Notice what's already in context.** `AGENTS.md` / `CLAUDE.md` (root and
   nested, path-scoped) are typically already loaded — use them for the repo's
   test conventions, where verification lives, and what "correct" means for its AI
   features. Also read any `evals/README`, `CONTRIBUTING`, or testing doc rather
   than re-deriving conventions.
2. **Read the profile if present:** `.agents/profiles/eval-author.md`. If it
   exists, apply its frontmatter knobs (`model`, `budget`, `fan_out`,
   `focus_paths`, `ignore_paths`, plus `eval_dir`, `dataset_dir`, `judge_model`,
   `run_cmd`) and its `## ADD` / `## OVERRIDE base:<id>` / `## SUPPRESS base:<id>`
   directives against the checklist in `references/checklist.md`. A SUPPRESSed id
   is never scaffolded/flagged; an OVERRIDDEN one uses the project's rebinding
   (e.g. point the judge at the repo's own grader).
3. **Resolve commands** in this precedence, first hit wins: profile `commands` /
   `run_cmd` → introspect the repo (`package.json` test/eval scripts,
   `pyproject.toml`, `Makefile`, `.github/workflows`, existing `evals/` runner) →
   **ask the user once** if still ambiguous → ecosystem default. The inventory
   script reports `run_hints`; use them. Never invent a run command.
4. **Fall back to defaults** when no profile and no convention exist — the skill
   must run usefully with zero config. The fallback layout is in
   `references/harness-wiring.md`.

Honor the budget posture from the start: `fan_out: never` ⇒ stay single-pass;
`fan_out: ask` ⇒ cost-preflight before any multi-agent step; a cheaper `model` ⇒
lean on the inventory script's numbers and lower-freedom scripted scaffolding;
a more capable `model` ⇒ more latitude in rubric/dataset authorship.

## Workflow

> Only load the reference file a step needs:
> `references/checklist.md` (the `base:<id>` contract),
> `references/eval-taxonomy.md` (test vs output-eval vs trajectory-eval vs LM-judge — which to pick),
> `references/rubric-design.md` (anchored scoring, calibration, bias control),
> `references/dataset-construction.md` (labelled/golden sets, edge+adversarial, no leakage),
> `references/harness-wiring.md` (layout + runner contract + CI tiering),
> `references/report-template.md` (the deliverable shape).

### 1. Inventory what is verified vs not (deterministic, not by eyeball)

Run the bundled discovery helper — it self-roots via `git rev-parse --show-toplevel`,
so it works from any subdirectory:

```bash
python3 "<path-to-skill>/scripts/eval_inventory.py" --json
```

It reports existing test/eval homes, the project's `run_hints`, and two lists of
**unverified surfaces**: deterministic (no name-matching test) and non-deterministic
(touches an LLM/agent/prompt surface with no eval reference). **These are priors,
not verdicts** — a listed file may already be covered under another name; a missed
one may hide. Confirm before scaffolding. If the user named a specific feature,
scope to it; otherwise rank by risk (the AI-facing, user-visible, money/safety
surfaces first).

### 2. Classify each surface — test or eval (the load-bearing call)

For each surface in scope, apply the one decision from
`references/eval-taxonomy.md`:

> Is the output a function of the input alone (same input → same output, no
> model/sampling in the path)?

- **Deterministic → TEST** (`base:test-deterministic-only`): pure functions,
  parsers, validators, routers, tool wrappers, schema enforcement, reducers.
- **Non-deterministic → EVAL** (`base:trajectory-and-output-eval`,
  `base:eval-output-quality`): the model's generated output, and — for an agent
  (**Agent = Model + Harness**) — its **trajectory** (tool choice, ordering,
  budget, safety invariants), which is a *separate* axis from the output.

Most features are a pipeline of both: test the deterministic glue, eval the
generative core. Do not exact-match stochastic output and call it a test, and do
not rubric a pure function. **Climb to the cheapest mechanism that actually
measures the property** — programmatic check before metric before LM-judge; a
judge call for something a program could check (valid JSON, real citation id) is
waste and adds variance.

### 3. Build the labelled dataset (per non-deterministic surface)

Per `references/dataset-construction.md`, assemble a **held-out, labelled** set as
versioned data (JSONL/YAML under the discovered/`evals/` dataset dir), one
self-describing case each (input, pinned context, expected, label rationale, tags,
source). Deliberately span the coverage matrix — happy-path **plus** edge cases,
**adversarial** inputs (injection, ambiguous, out-of-scope), **regression seeds**
(every known past failure frozen as a case), and **negative/refusal** cases
(`base:dataset-labeled`, `base:dataset-edge-and-adversarial`). Hold the set out
from prompts/fine-tune data and don't let the model under test author its own
answer key (`base:dataset-no-leakage`). A small, sharp, well-labelled set (~20–50
cases heavy on edge+regression) beats a large noisy one. **Pin the dynamic
context** in each case so the eval measures the model, not today's flaky retrieval.

Where a label is genuinely undefined — "correct" was never specified — **stop and
flag it**: that is a specification gap, the input to `spec-author`, not something
to invent here.

### 4. Write the rubric and (if needed) wire the LM-judge

Per `references/rubric-design.md`, every non-deterministic check scores against a
**written, version-controlled rubric** with named criteria and **anchored levels**
(`base:rubric-explicit`, `base:rubric-anchored`) — never a bare "is this good?".
Pick criteria from the surface's spec (correctness, faithfulness/groundedness,
format adherence, refusal correctness, trajectory safety), state the decision rule
and threshold (`base:eval-thresholds`).

Use an LM-judge **only** for qualities a program can't compute, and make it a
measurement (`base:llm-judge-calibrated`): pin the rubric in the judge prompt, use
a **different model/config** than the one under test, demand structured justified
output, control for position/length/self-preference bias, and **calibrate against
human labels** on a sample (keep a `calibration.jsonl`, report the agreement
rate). An uncalibrated judge is an opinion, not a measurement — say so if you can't
calibrate yet.

### 5. Scaffold tests for the deterministic surfaces

Write the deterministic tests in the project's **existing test tree** (not under
`evals/`), mirroring its framework and async patterns. Pin the **observable
contract** (`base:test-pins-contract`), and cover the behavior that actually breaks
— boundaries, error paths, each seam — not just the happy path
(`base:test-boundary`). Each test must be a real regression test: it fails on a
known-bad implementation and passes on the correct one (`base:no-vacuous-eval`).

### 6. Wire the runnable harness (human-approval pause before any write)

Per `references/harness-wiring.md`, **discover the layout before imposing one**
(profile → existing eval/test home → the framework in use → the project's gate →
fallback layout). The runner must load the dataset as data, pin and **record the
model/prompt/dataset version**, score by the rubric's mechanism, aggregate
per-bucket, apply the threshold, and **exit non-zero when the floor is breached**
so it can gate (`base:eval-runnable`, `base:eval-deterministic-harness`). The
harness's own deterministic logic (loading, scoring math, threshold) gets a unit
test — `tests-and-evals` applied to the eval tooling itself.

Wire it where the project runs checks, **cost-aware**: deterministic tests on every
PR; LLM evals on a labelled tier (cheap smoke subset per PR + full set nightly /
pre-release / on-label) — never silently bill every PR for LLM calls and never drop
evals from CI entirely (`base:wire-runnable`). State the exact run command.

**Pause for explicit approval before writing files, committing, or anything that
spends** (LLM calls during a calibration/demo run cost money). This repo never
mutates or spends silently: create scaffolding, then stop and confirm before any
`git add` / commit / push or any judge run that incurs cost. Default to *not*
committing unless asked; never push to a protected branch.

### 7. Prove it can fail, then report honest coverage

Before declaring an eval done, **demonstrate the failing case**
(`base:no-vacuous-eval`): run the rubric/test on a seeded known-bad output → it
must fail on the right criterion; on the good output → it passes. An always-green
check is rejected. Run the suite for real where budget allows.

Write the coverage report per `references/report-template.md` to a file
(`eval-coverage.md` or a user-named path), incrementally: the coverage matrix with
**every surface as the denominator** (`base:report-coverage`,
`base:coverage-honest`), what is now verified, **what is still not**, the real run
results, and the exact command. Show only real runs or label cases
`pending-labels` / `needs-human` — **never paste a green score you did not
produce** (`base:report-no-fabrication`). Surface the handoffs (spec gaps →
spec-author; harness/config risks → harness-audit). Emit a ≤6-line summary inline.

### 8. Budget & fan-out posture (cost preflight before any multi-agent run)

**Single-pass single-agent is the default** — the inventory script does the heavy
deterministic work and one pass usually suffices. Multi-agent fan-out (e.g. one
agent per surface to draft datasets/rubrics in parallel on a large repo) is
**opt-in and budget-gated**. Before spawning any subagent **or** running any
cost-incurring LLM/judge batch:

- State the cost: "this is ~N subagents and/or ~M judge calls at `<model>` —
  proceed?" and **honor `fan_out`**: `never` → single-pass only; `ask` → wait for
  a yes; `allowed` → proceed and announce the count. Honor `budget` and `model`
  (a cheaper model → lean, scripted, minimal judge calls; a more capable model with headroom →
  fan-out and richer authorship are fine).
- Fan out only when the repo is large enough to warrant it and the profile
  permits. Each subagent returns scaffolding/findings and **edits nothing**
  outside its assigned surface.

### 9. Self-check / quality gate (run before reporting)

Verify every box — report the **literal** results, do not assert:

- [ ] Both kinds are covered for the surfaces that exist: deterministic → tests,
      non-deterministic → evals (`base:tests-and-evals-both`). If only one kind of
      surface exists, that is stated.
- [ ] Every test/eval **can fail**: demonstrated on a seeded known-bad
      input/output, passes on the correct one (`base:no-vacuous-eval`). No
      always-green check shipped.
- [ ] Each surface was classified correctly — no exact-match "test" over stochastic
      output, no rubric over a pure function (`base:test-deterministic-only`,
      `base:trajectory-and-output-eval`). Tests pin the observable contract and cover
      boundaries/error paths (`base:test-pins-contract`, `base:test-boundary`);
      output evals score the qualities the surface's spec names
      (`base:eval-output-quality`).
- [ ] Every non-deterministic check scores against a written, **anchored** rubric;
      no bare "is this good?" (`base:rubric-explicit`, `base:rubric-anchored`).
- [ ] Datasets are **labelled, held-out, and edge+adversarial+regression** — not
      happy-path-only, not leaked (`base:dataset-labeled`,
      `base:dataset-edge-and-adversarial`, `base:dataset-no-leakage`).
- [ ] Any LM-judge runs from a pinned rubric, uses a different model/config than
      the surface under test, and reports a **human-agreement** number — or is
      explicitly labelled uncalibrated (`base:llm-judge-calibrated`).
- [ ] The suite is **runnable** with a stated command, exits non-zero on a breached
      threshold, records model/prompt/dataset version, and is wired cost-aware into
      the gate (`base:eval-runnable`, `base:eval-thresholds`,
      `base:eval-deterministic-harness`, `base:wire-runnable`).
- [ ] The coverage report shows the **full denominator** and states what is NOT
      verified as plainly as what is (`base:report-coverage`,
      `base:coverage-honest`).
- [ ] **No fabricated results** — only real runs or `pending-labels`/`needs-human`
      cases (`base:report-no-fabrication`).
- [ ] No write/commit/spend happened without the approval pause; any fan-out or
      judge batch was cost-preflighted and honored `fan_out`.
- [ ] **No code under test was modified** — a real bug found during inventory was
      reported and handed off (`bug-swarm`), not fixed here.
- [ ] **Stayed in lane** — spec gaps (`spec-author`), harness/config risks
      (`harness-audit`), and danger-surface hooks (`guardrail-author`) were surfaced
      as handoffs, not acted on.
- [ ] **Shell-safe** emitted commands — heredoc / single-quote bodies, exit codes
      checked directly, no gate piped to `tail`/`head`.
- [ ] Heavy deliverable is in files; inline output is a ≤6-line summary + path.

If any box fails, fix it or call it out explicitly — do not report a partial gate
as complete.

## Guardrails

- **Scaffold and report — never fabricate.** This skill writes verification and an
  honest coverage read. It never pastes a passing score it did not produce, never
  rounds an unverified surface up to "covered", and never green-washes the report.
- **Right tool for the surface.** Deterministic → test; non-deterministic → eval.
  An exact-match assertion over model output is an eval mis-filed as a test; a
  rubric over a pure function is theater. Classify before scaffolding.
- **Every check must be able to fail.** Demonstrate the failing case. An
  always-green test/eval is worse than none — it manufactures false confidence.
- **Don't fix the code under test.** If the inventory reveals a real bug, report it
  and hand off (`bug-swarm` to fix one failing test); this skill verifies, it does
  not repair.
- **Stay in your lane.** Don't author the spec that defines "correct"
  (`spec-author`); don't audit the agent's harness/tool/guardrail config
  (`harness-audit`); don't build a deterministic fail-closed hook that BLOCKS a
  danger surface (`guardrail-author` — evals *measure*, guardrails *prevent*);
  don't review a diff (`code-review`); don't fix one failing test (`bug-swarm`).
  Surface those as handoffs.
- **No silent spend or mutation.** LLM/judge runs cost money and writing files
  changes the tree — both pause for approval. Cost-preflight any fan-out or judge
  batch; honor `fan_out` and `budget`.
- **Shell-safety** for any emitted commands: single-quote or heredoc bodies
  (backticks run command substitution on zsh), check exit codes directly, never
  pipe a gate to `tail`/`head` (it masks the exit code).

## References

Only load the reference files you need:

- `references/checklist.md` — the stable `base:<id>` contract profiles
  OVERRIDE/SUPPRESS (tests-and-evals-both, no-vacuous-eval, rubric/dataset/judge
  ids, coverage-honest, …).
- `references/eval-taxonomy.md` — test vs output-eval vs trajectory-eval vs
  LM-judge, the decision tree, and the cheapest-mechanism ladder.
- `references/rubric-design.md` — anchored scoring, the criteria menus, LM-judge
  calibration and bias control, the rubric self-test.
- `references/dataset-construction.md` — labelled/golden sets, the coverage matrix
  (edge/adversarial/regression/refusal), leakage smells, sizing.
- `references/harness-wiring.md` — layout discovery, the runner contract, CI
  tiering, thresholds, reproducibility hooks.
- `references/report-template.md` — the coverage-report shape and the inline
  summary.
