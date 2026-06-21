# Harness wiring — where evals live and how the project runs them

Load when scaffolding the layout and the run command (Workflow Step 6). The
deliverable is **runnable** (`base:eval-runnable`, `base:wire-runnable`): a suite
nothing can execute is documentation, not verification. The harness must also be
**deterministic itself** (`base:eval-deterministic-harness`) — the thing it
measures is stochastic, but loading the dataset, scoring, aggregating, and
threshold-checking must be repeatable so a green/red result is trustworthy.

This skill **adapts to the repo's existing structure first** — discover, don't
impose. The layout below is the fallback when no convention exists.

## Discover before you scaffold (precedence, first hit wins)

1. **Profile** `.agents/profiles/eval-author.md` → `eval_dir`, `dataset_dir`,
   `run_cmd`, `judge_model`.
2. **Existing eval/test homes** — what `eval_inventory.py` reported under
   `existing_eval_dirs` / `existing_test_dirs`. If the repo already has
   `evals/` or co-located `*.eval.ts` etc., **match it exactly** (naming,
   framework, runner).
3. **The test framework already in use** — pytest, vitest/jest, go test, rspec.
   Evals that are really parametrized cases often ride the existing runner
   (`pytest evals/`, a `test.concurrent` describe block) — cheapest to wire and
   discover.
4. **The project's gate** — `package.json` scripts, `Makefile`, `pyproject.toml`,
   CI workflow files. Add the eval target *there*, next to the existing checks.
5. **Fallback layout** (below) only when none of the above exists — and say in the
   report that you introduced a new convention.

## Fallback layout (stack-agnostic)

```
evals/
  README.md                 # what each suite covers + the run command
  <suite-name>/
    dataset/                # labelled cases (JSONL/YAML) — see dataset-construction.md
      cases.jsonl
      calibration.jsonl     # human-labelled subset for LM-judge calibration
    rubric.md               # anchored criteria + levels + decision rule + threshold
    run_eval.<ext>          # loads dataset -> runs surface -> scores -> threshold -> report
    judge_prompt.md         # pinned LM-judge prompt (if a judge is used)
    results/                # gitignored or committed-as-history per project policy
tests/                      # deterministic tests stay in the project's normal home
```

Keep **deterministic tests in the project's existing test tree** — do not move
them into `evals/`. The split mirrors the framework: `tests/` = deterministic,
`evals/` = non-deterministic. Co-locating them blurs the line the whole skill
rests on.

## The runner contract (so results are trustworthy)

`run_eval` (or the parametrized test) must:

1. **Load the dataset as data** — never hardcode cases in the runner; the dataset
   is the labelled source of truth and must be diffable.
2. **Pin static context** — model version, system prompt, tool defs, few-shot —
   and **record the model version in the result** so two runs are comparable
   (`base:eval-deterministic-harness`). Pin temperature/seed where the platform
   allows.
3. **Score each case** by the rubric's mechanism (programmatic check → metric →
   LM-judge, cheapest that measures the property — see `eval-taxonomy.md`).
4. **Aggregate per bucket and overall**, apply the **threshold**
   (`base:eval-thresholds`), and exit non-zero when the floor is breached so it
   can gate.
5. **Emit a machine-readable result** (per-case scores + aggregates + model
   version + judge agreement) so trends are trackable run-to-run, plus a short
   human summary.
6. **Be idempotent and offline-capable for its deterministic parts** — dataset
   loading, scoring math, and threshold logic must run and be unit-testable
   without any model call (you can stub the model with recorded outputs). The
   harness's own logic gets a deterministic **test**; this is `tests-and-evals`
   applied to the eval tooling itself.

## Wiring into the gate (cost-aware — this is the load-bearing tradeoff)

LLM evals cost money and latency; deterministic tests don't. Wire accordingly and
**state the cost posture** (`base:wire-runnable`):

- **Deterministic tests** → the normal per-commit/per-PR test gate. No reason to
  defer; they're fast and free.
- **Evals (LLM in the loop)** → choose a tier and label it explicitly:
  - **Every PR** only if fast/cheap enough, or run a **cheap subset** (smoke
    eval: a few cases per bucket) per PR + the full set on a schedule.
  - **Nightly / pre-release / on-label** for the full, expensive set.
  - **Never** silently put a per-PR LLM bill in CI without flagging it, and never
    drop evals from CI entirely because they're slow — a defended-but-deferred
    eval beats an undefended fast one.
- **Always print the exact run command** in the README and the coverage report:
  e.g. `make eval`, `npm run eval`, `pytest evals/ -m eval`,
  `python3 evals/<suite>/run_eval.py --threshold 0.8`.

## Thresholds and gating

- Each eval declares a **pass floor** (absolute) and/or a **max-regression delta**
  (relative to the last committed baseline) — relative gating catches "we got 3%
  worse" that an absolute floor misses.
- Add **budget ceilings** (latency / tokens / dollars per run) as first-class
  thresholds — a correct-but-slow-and-expensive agent is a regression.
- Decide **block vs report**: a calibrated, low-variance eval can block; a new or
  noisy one reports-only until it earns trust. State which, per suite.

## Reproducibility hooks (what the eval should never forget)

Encode these as harness invariants — the framework's "what the agent should never
forget" applied to the eval itself:

- Record **model + prompt + dataset versions** with every result; a moved score
  with no recorded version is uninvestigable.
- Fail loudly on a **missing label / empty dataset / unreachable judge** — never
  silently score zero cases and report green (that is `base:no-vacuous-eval` at the
  harness level).
- Keep the **judge prompt and calibration set in version control** so a judge
  change is a reviewable diff, not an invisible drift.
