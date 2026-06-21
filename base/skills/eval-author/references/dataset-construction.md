# Dataset construction — the labelled set an eval scores against

Load when building or auditing an eval dataset (Workflow Step 3). An eval is only
as honest as the set it runs on. A dataset of easy, happy-path, leaked examples
produces a high score that means nothing — it is the "demo" the framework warns
against, dressed as an eval. The job: a **held-out, labelled, edge-and-adversarial
set** whose score you can actually trust.

## The three properties a trustworthy eval set has

1. **Labelled** (`base:dataset-labeled`) — every case carries a ground-truth
   expectation: an exact expected output, an expected score/level, a key-point
   set, an expected tool sequence, or an expected refusal. A case with no label
   can be scored for *consistency* but never for *correctness*. No label → it is
   not yet an eval case.
2. **Held out / no leakage** (`base:dataset-no-leakage`) — the set is disjoint from
   anything the system saw: not the few-shot/prompt examples, not fine-tuning
   data, not authored by the same model generation it grades. Leakage turns an
   eval into a memorization check that always passes.
3. **Representative + adversarial** (`base:dataset-edge-and-adversarial`) — it
   spans the real input distribution AND deliberately includes the hard cases that
   actually break things, not just the ones that flatter the system.

## Case schema (one row per case, version-controlled)

Keep cases as data (JSONL / YAML / CSV under `evals/<suite>/dataset/`), one self-
describing row each:

```jsonc
{
  "id": "refusal-injection-003",       // stable, human-readable
  "input": { /* the exact input to the surface */ },
  "context": { /* pinned dynamic context: retrieved chunks, tool results, prior turns */ },
  "expected": { /* gold output, expected score, key-points, or expected tool path */ },
  "label_rationale": "why this is the right answer (1 line — forces honest labels)",
  "tags": ["edge", "adversarial", "regression", "happy-path"],
  "source": "synthetic | sampled-prod (anonymized) | hand-authored | past-incident",
  "min_score": 2                        // optional per-case threshold override
}
```

Pinning `context` is what makes the eval reproducible — it measures the model, not
today's flaky retrieval (see `eval-taxonomy.md` → static vs dynamic context). To
evaluate retrieval itself, give it its **own** dataset and eval.

## Coverage matrix — span these deliberately, don't just collect easy cases

| Bucket | What it catches | Aim for |
|---|---|---|
| **Happy path** | Baseline competence | Enough to be representative — but not the whole set. |
| **Edge cases** | Boundaries: empty, max-length, unicode, ambiguous, multi-intent, out-of-scope | A real share — this is where quality actually varies. |
| **Adversarial** | Prompt injection, jailbreaks, contradictory instructions, data exfil attempts, "ignore the system prompt" | Explicit cases — a suite with zero adversarial cases hasn't tested safety. |
| **Regression seeds** | Every past production failure, frozen as a case | One per real incident — this is how an eval stops a bug from coming back (`base:no-vacuous-eval`'s sibling at the dataset level). |
| **Negative / refusal** | Things the system should NOT do or should refuse | Without these, a model that does too much scores as well as a correct one. |
| **Distribution edges** | Rare-but-real inputs (long context, non-English, domain jargon) | A few, weighted by real-world cost of failure. |

A score is only as meaningful as the buckets it covers. Report the per-bucket
breakdown, not just the aggregate — 95% overall with 40% on adversarial is a
safety hole the headline number hides.

## Labelling discipline

- **One labeller ≠ ground truth for hard cases.** For subjective labels, have ≥2
  independent labellers and record agreement; reconcile disagreements into a
  documented rule (which then sharpens the rubric).
- **The rationale field is load-bearing.** Forcing a one-line reason per label
  surfaces cases that are actually ambiguous or mis-labelled — fix or drop those
  before they poison the score.
- **Anonymize sampled production data** — strip PII before it enters a checked-in
  dataset. A real-traffic eval set is gold; a PII leak in the repo is a breach.
- **Version the dataset** and treat additions like code: a case added to make a
  number go up (without a real label) is dataset gaming, the dataset-level twin of
  a vacuous eval.

## Sizing — start small and honest, grow with signal

- A **small, well-labelled, well-targeted** set beats a large noisy one. ~20–50
  sharp cases (heavy on edge + regression) is a legitimate first eval and far more
  useful than 1,000 unlabelled rows.
- Grow it from **real signal**: every production miss becomes a regression case;
  every disagreement in labelling becomes a clarified rule.
- For an LM-judge, you also need a **calibration subset with human labels**
  (`base:llm-judge-calibrated`) — keep it separate and checked in.

## Leakage smells to check before trusting a score

- The eval inputs appear verbatim in the prompt's few-shot block, or in fine-tune
  data → memorization, not generalization.
- The "gold" answers were generated by the same model the eval grades → it is
  grading its own homework.
- The eval set was filtered to cases the system already handles → survivorship
  bias inflates the score.
- The judge's rubric examples are drawn from the eval set itself → the judge has
  seen the answer key.

If any smell is present, the number is not measuring what it claims — fix the set
before reporting the score, and say so in the coverage report (`base:coverage-honest`).
