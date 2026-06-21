# Eval taxonomy — pick the right verification for each surface

Load when classifying a surface (Workflow Step 2). The governing rule from the
New-SDLC framework: **tests verify the deterministic parts; evals verify the
non-deterministic parts.** Misclassifying is the most common failure — an
exact-match "test" over model output is flaky and worthless; a rubric over a pure
function is theater. Classify first, then scaffold.

## The one decision that drives everything

> Is the output a **function of the input alone** (same input → same output,
> every time, no model/sampling/network-nondeterminism in the path)?

- **Yes → it is deterministic → write a TEST.** Cheap, fast, exact, gates every
  commit. (`base:test-deterministic-only`)
- **No → it is non-deterministic → write an EVAL.** Score with tolerance: a
  rubric, a metric, or an LM-judge against a labelled set. (`base:eval-*`)

Most real features are a *pipeline of both*. The deterministic glue (parsing,
routing, validation, tool I/O, schema enforcement) is tested; the generative core
(the model's answer, the agent's plan) is evaled. Verify each segment with its own
kind — do not let the stochastic core force you to eval the deterministic glue,
and do not pretend the stochastic core is deterministic to force a test.

## The four kinds

| Kind | Verifies | Mechanism | When |
|---|---|---|---|
| **Test** | Deterministic logic | Exact assert: input X → output Y | Pure functions, parsers, validators, routers, tool wrappers, schema enforcement, reducers — anything repeatable. |
| **Output eval** | Quality of a generated artifact | Score the final output vs a labelled expectation: programmatic metric, rubric, or LM-judge | Summaries, answers, classifications, extractions, rewrites, generated code/SQL — single-shot generation. |
| **Trajectory eval** | Quality of the *path* an agent took | Score the action/tool sequence vs an expected-behavior spec | Multi-step agents: did it call the right tools, in a sane order, within step/cost budget, with no forbidden action? |
| **LM-judge** | A quality that has no programmatic checker | A different model scores the output against a written, anchored rubric; calibrated to human labels | Faithfulness, helpfulness, tone, "did it answer the question" — graded, not computed. A scoring *mechanism*, used inside output/trajectory evals. |

## Prefer the cheapest mechanism that actually measures the property

Climb this ladder; only ascend when the rung below genuinely can't capture the
property. Each rung up costs more money, more flakiness, and more calibration
burden.

1. **Deterministic test** — if any part is exactly checkable, test it exactly.
2. **Programmatic output check** — exact match, regex, JSON-schema validity,
   set/F1 against a gold label, `assertEqual` on a normalized form, a
   compile/exec check for generated code, "the SQL returns the expected rows".
   Fast, free, non-flaky. Use it wherever the property is computable.
3. **Reference-based metric** — similarity/overlap to a reference answer
   (embedding similarity, ROUGE/BLEU-style, exact-set recall). Use when "close to
   the gold answer" is meaningful and a hard match is too strict.
4. **LM-judge against a rubric** — only for qualities a program can't compute
   (faithfulness, coherence, helpfulness, tone). The most expensive and
   highest-variance rung — and it MUST be calibrated (`base:llm-judge-calibrated`)
   or it is just a second opinion with a confidence costume.

A property that is programmatically checkable should **never** be sent to an
LM-judge. "Is it valid JSON?" / "does it cite a real source id?" / "is the number
within tolerance?" are code, not judge calls — cheaper, deterministic, and not
subject to the judge's own drift.

## Agent = Model + Harness → eval BOTH axes

For any agentic surface, a correct final answer is **not** sufficient evidence of
a working agent — it may have reached the answer by luck, by an unsafe shortcut,
or by burning 40 tool calls. Evaluate two axes (`base:trajectory-and-output-eval`):

- **Output axis** — was the final artifact correct/useful? (output eval)
- **Trajectory axis** — was the path sane?
  - **Tool selection** — right tools chosen, wrong tools avoided.
  - **Ordering / efficiency** — sane sequence, no thrash/loops, bounded steps.
  - **Budget** — within step / token / latency / dollar ceiling.
  - **Safety invariants** — no forbidden action (no write on a read-only task, no
    egress of secrets, no skipped human-approval gate).
  - **Recovery** — on a tool error, does it recover or spiral?

"Most agent failures are configuration failures." A trajectory eval is how those
config failures (wrong tool exposed, missing guardrail, bad system prompt) become
*visible and regression-gated* instead of showing up in production.

## Static vs dynamic context — what the eval must hold fixed

Generated output depends on the **context** assembled at run time, so an eval is
only reproducible if it pins that context:

- **Static context** (system prompt, tool definitions, few-shot examples, model
  version) — pin it in the eval and **version it**; a silent prompt edit that
  moves the score must be attributable. Record the model version with every run.
- **Dynamic context** (retrieved docs, tool results, prior turns) — fix it in the
  dataset (record the exact retrieved chunks / tool outputs the case ran with) so
  the eval measures the model, not today's flaky retrieval. To test retrieval
  itself, that becomes its **own** eval with its own labelled set.

If the eval's score moves and you can't tell whether the model, the prompt, or the
retrieval changed, the context wasn't pinned — fix that before trusting any number.

## Anti-patterns (each is a `base:no-vacuous-eval` violation in disguise)

- **Exact-matching stochastic output** — a "test" asserting the model returns one
  exact string. Flakes immediately; reclassify as an eval with rubric/tolerance.
- **Self-graded judge** — the model under test grades its own output with no
  calibration. Conflict of interest; use a different model/config and calibrate.
- **Unlabelled "eval"** — scoring live traffic with no ground truth. You can
  measure *consistency*, never *correctness*. Needs a labelled set.
- **Always-green rubric** — a rubric whose top level is trivially earned, so every
  output passes. Show it fails on a known-bad output first.
- **Demo as eval** — one hand-picked happy-path example. Set the bar at the eval
  (a held-out, adversarial, labelled set), not the demo.
- **Threshold-free score** — a number printed with no pass floor; it can't gate,
  so it protects nothing.
