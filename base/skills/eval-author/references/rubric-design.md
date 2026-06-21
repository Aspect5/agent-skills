# Rubric design — making a non-deterministic check trustworthy

Load when authoring a scoring rubric or wiring an LM-judge (Workflow Step 4/5). A
rubric turns "is this good?" — an opinion — into a measurement two graders
converge on. An unwritten or unanchored rubric produces numbers that look rigorous
and mean nothing. The bar: another competent grader (human or a different model)
applying your rubric to the same output lands on the same score.

## What a usable rubric requires

1. **Named criteria, not a vibe.** Decompose "quality" into the specific
   properties that matter for *this* surface, drawn from its spec. Score each
   independently; a single 1–10 "overall" score is unanchorable and
   uninterpretable. (`base:rubric-explicit`)
2. **Anchored levels per criterion.** Every criterion gets discrete levels
   (recommended: 0/1/2 or fail/partial/pass) with a **concrete description of what
   earns each level** and, where feasible, a worked example. "2 = fully grounded:
   every claim traces to a provided source; 1 = mostly grounded: one unsupported
   aside; 0 = contains a claim absent from or contradicting the sources."
   (`base:rubric-anchored`)
3. **A decision rule.** How criteria combine into pass/fail: a weighted sum with a
   floor, or hard gates ("any 0 on a safety criterion = fail regardless of the
   rest"). State it; don't leave aggregation implicit.
4. **A threshold.** The score at/above which the case passes, and whether the eval
   **blocks** the build or only reports. (`base:eval-thresholds`)

## Criteria menus (pick from the surface's spec, don't run them all)

Choose the few that matter for the surface; an irrelevant criterion is noise that
dilutes the signal.

**Answering / chat / Q&A**
- *Correctness* — factually right against the labelled answer.
- *Faithfulness / groundedness* — every claim is supported by the provided
  context; no hallucinated facts (programmatically check citation ids where you
  can, before sending the rest to a judge).
- *Completeness* — covers what the question actually asked.
- *Relevance* — no off-topic padding.
- *Refusal correctness* — refuses what it should, answers what it should (a model
  that refuses everything scores high on safety and is useless).

**Summarization / extraction / rewrite**
- *Coverage* of the salient points (against a labelled key-point set).
- *Faithfulness* — nothing added that isn't in the source.
- *Format adherence* — length, structure, schema (programmatic where possible).

**Generated code / SQL / structured output**
- *Validity* — parses / compiles / matches the JSON schema (programmatic — never a
  judge call).
- *Functional correctness* — passes the reference tests / returns the expected
  rows (programmatic).
- *Quality* — only the parts a program can't check (idiomatic, no obvious smell) →
  judge.

**Agent trajectory** (see `eval-taxonomy.md` for the axes)
- *Tool-selection correctness*, *step efficiency*, *budget adherence*, *safety
  invariants*, *error recovery* — most of these are **programmatic** over a
  recorded trace; reserve the judge for "was the plan reasonable".

**Cross-cutting (almost always include)**
- *Safety* — no PII leak, no injection-following, no forbidden content. Often a
  hard gate, often programmatically checkable.

## LM-judge: make it a measurement, not a second opinion

An LM-judge is the most expensive, highest-variance rung — earn it
(`base:llm-judge-calibrated`):

- **Pin a written rubric** in the prompt — the exact anchored criteria above, not
  "rate 1–10". The judge prompt is version-controlled next to the eval.
- **Use a different model/config than the one under test.** A model grading its own
  output has a conflict of interest and inflates. Where the platform allows, pin
  the judge's temperature low and its version explicitly.
- **Demand structured, justified output** — `{criterion: level, evidence: "<quote
  from the output>"}` — so a score is auditable and you can spot a judge that
  rationalizes backwards.
- **Calibrate against human labels.** Hand-label a sample (start ~20–50 cases),
  run the judge, and **report agreement** (% exact, or Cohen's κ). Below your
  agreement bar, the judge is not trustworthy: tighten the rubric and re-measure.
  Keep the calibration set checked in so calibration is repeatable.
- **Control for known biases** — position bias (randomize order in pairwise
  judging), length bias (longer ≠ better; anchor against it), self-preference, and
  leniency drift. Mitigate in the rubric and verify in calibration.
- **Re-calibrate when anything moves** — judge model upgrade, rubric edit, or
  surface change invalidates the old agreement number.

## Reduce variance so a score means something run-to-run

- Score **each criterion separately**, then aggregate by your decision rule —
  finer-grained scores have lower variance than one holistic guess.
- Prefer **discrete anchored levels** over a continuous 1–10 (humans and models
  both anchor better).
- For ranking two candidates, **pairwise comparison** ("is A or B better, and
  why") is usually more reliable than independent absolute scores — but randomize
  position.
- Run the judge **N times and aggregate** (majority / mean) on high-variance
  criteria; report the spread, not just the point estimate.
- **Seed/version everything** so a moved score is attributable to a real change,
  not sampling noise (`base:eval-deterministic-harness`).

## Self-test the rubric before trusting it (`base:no-vacuous-eval`)

Before a rubric protects anything, prove it discriminates:

- Run it on a **known-good** output → it should pass.
- Run it on a **known-bad** output (seed one deliberately: drop a fact, inject an
  unsupported claim, break the format) → it should fail, on the right criterion.
- If both score the same, the rubric is vacuous — the levels aren't anchored
  enough or the criteria miss the property. Fix it before shipping the eval.
