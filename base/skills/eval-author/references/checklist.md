# Eval-author checklist (stable `base:<id>` ids)

The contract surface of this skill. Every `base:<id>` referenced in `SKILL.md`
is defined here; a project profile (`.agents/profiles/eval-author.md`) rebinds or
silences any id:

- `## OVERRIDE` → `base:<id> → <new rule>` rebinds a check (e.g. point the judge
  at the project's own grader).
- `## SUPPRESS` → `base:<id>` turns a check off (e.g. a repo with no
  non-deterministic surface SUPPRESSes the eval-only ids).
- `## ADD` → appends project-specific checks (give them project ids, not `base:`).

```markdown
## OVERRIDE
- base:llm-judge-calibrated → judge model is pinned to our internal grader v3; calibration set lives in evals/judge_calibration/
## SUPPRESS
- base:trajectory-and-output-eval   # this repo has no agent loop — output evals only
## ADD
- proj:pii-redaction-eval → every generated-output eval also asserts no raw PII leaks
```

> Load this file when deciding **what** to scaffold and when running the
> self-check. The ids are the contract — do not renumber them.

These split into two families the New-SDLC framework keeps separate:
**deterministic logic is verified by TESTS; non-deterministic output/trajectory
is verified by EVALS.** A suite that only has one half is incomplete by
construction.

## Coverage & honesty (`base:coverage-*`, `base:tests-and-evals-both`) — always

- `base:tests-and-evals-both` — The suite covers **both** kinds of surface that
  exist in the repo: deterministic logic gets tests, non-deterministic
  output/trajectory gets evals. If only one kind of surface exists, say so; if
  both exist and only one is covered, that is the headline gap.
- `base:coverage-honest` — The coverage report states what is **NOT** verified as
  plainly as what is. The denominator is the inventory (every surface), not just
  the files you touched. Never round an unverified surface up to "covered". An
  honest "0% of the agent's trajectory is evaled" is a valid, valuable output.
- `base:no-vacuous-eval` — Every test/eval must be able to **fail**. It fails on a
  known-bad input/output and passes on the correct one. A check that is green no
  matter what (asserts on a mock's own return, judges with an always-"PASS"
  rubric, scores an empty dataset) is worse than no check — it manufactures false
  confidence. Demonstrate the failing case before declaring the eval done.
- `base:eval-runnable` — The scaffolded suite runs with a single discoverable
  command, wired into the project's own gate (or a clearly-labelled new target).
  A rubric in a markdown file that nothing executes is documentation, not an eval.

## Tests — deterministic surfaces (`base:test-*`)

- `base:test-deterministic-only` — Tests are reserved for genuinely deterministic
  behavior: same input → same output, no model/sampling in the path. Do not write
  a brittle exact-match "test" over LLM output and call it a test — that is an
  eval, and it belongs in the eval suite with tolerance/rubric scoring.
- `base:test-boundary` — The deterministic tests pin the behavior that actually
  breaks: boundaries (empty, null, max, negative, unicode), error paths, and the
  contract at each seam — not just the happy path.
- `base:test-pins-contract` — A test asserts on the **observable contract**
  (return value, emitted event, state change), not an internal detail that
  refactors will churn. It must survive a correct refactor and fail a real
  regression.

## Evals — non-deterministic surfaces (`base:eval-*`, `base:rubric-*`, `base:dataset-*`, `base:llm-judge-*`)

- `base:trajectory-and-output-eval` — For an agent (Model + Harness), evaluate
  **both** axes the framework names: the **output** (was the final answer/artifact
  correct/useful?) **and** the **trajectory** (did it take a sane path — right
  tools, no thrash, no forbidden action, bounded steps/cost?). A correct answer
  reached by a broken trajectory is a latent failure; flag if only one axis is
  covered.
- `base:eval-output-quality` — Generated-output evals score the qualities that
  matter for this surface (correctness, faithfulness/groundedness, format
  adherence, safety/refusal behavior, tone if specified) — chosen from the
  surface's spec, not a generic list.
- `base:rubric-explicit` — Every non-deterministic check scores against a
  **written, explicit rubric** with named criteria and anchored levels — never a
  bare "is this good?". The rubric is version-controlled next to the eval. An
  unwritten standard is not a standard.
- `base:rubric-anchored` — Each rubric criterion has **anchored levels** (e.g.
  0/1/2 or fail/partial/pass) with a concrete description of what earns each
  level, so two graders (human or model) converge. Anchors include at least one
  worked example per level where feasible.
- `base:dataset-labeled` — Evals run against a **labelled/golden dataset** with
  expected outputs or expected scores — not live, unlabelled traffic you can't
  grade. Each case records input, expected, and a one-line rationale for the
  label.
- `base:dataset-edge-and-adversarial` — The dataset deliberately includes edge
  cases, known past failures (regression seeds), and adversarial inputs (prompt
  injection, ambiguous, out-of-scope) — not just easy happy-path examples that
  inflate the score.
- `base:dataset-no-leakage` — The eval set is **held out**: it is not the
  few-shot/prompt examples, not the fine-tuning data, and not authored by the same
  generation the eval is grading. Leakage turns an eval into a memorization check.
- `base:llm-judge-calibrated` — When an LM-judge does the scoring, it is
  **calibrated against human labels** on a sample (agreement reported), runs from
  a **pinned, written rubric** (`base:rubric-explicit`), and — where it matters —
  a **different model/config** than the one under test grades it (a model grading
  itself is a conflict of interest). Report the judge model and the
  human-agreement rate; an uncalibrated judge is an opinion, not a measurement.
- `base:eval-thresholds` — Each eval declares a **pass threshold / budget**
  (score floor, max regression delta, latency/cost ceiling) so it can gate, plus
  whether it blocks the build or only reports. A score with no threshold cannot
  fail and therefore cannot protect anything.
- `base:eval-deterministic-harness` — The eval *harness* (dataset loading,
  scoring aggregation, threshold check, report) is itself deterministic and
  testable, so a green/red result is trustworthy even though the thing it measures
  is stochastic. Pin temperature/seed where the platform allows; record the model
  version with every run so results are reproducible and comparable over time.

## Wiring & reporting (`base:wire-*`, `base:report-*`)

- `base:wire-runnable` — The suite is wired where the project already runs checks
  (test runner config, a `make eval` / npm script target, a CI job). State the
  exact command. If evals are too slow/costly for every commit, wire them as a
  separate, clearly-labelled gate (nightly / pre-release / on-label) — never
  silently drop them from CI and never make every PR pay an LLM bill without
  saying so.
- `base:report-coverage` — The deliverable is a coverage read: per surface, which
  kind of verification now exists, what is still unverified, and the command to
  run it. Honest, with the denominator visible (`base:coverage-honest`).
- `base:report-no-fabrication` — This skill writes **scaffolding and reports
  coverage**; it does **not** invent passing results. Show real runs (including
  the demonstrated failing case from `base:no-vacuous-eval`) or label a case
  `pending-labels` / `needs-human` — never paste a green score you did not
  produce. A fabricated pass is the worst possible output of an eval skill.
