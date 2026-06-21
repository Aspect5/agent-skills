# Eval handoff — mapping every criterion to a test or an eval

A spec is only executable if its correctness is *measurable*. The bridge from spec to
build runs through verification: each acceptance criterion and each defined edge case is
handed to a future test or eval, so nothing in the contract is left unchecked. This file
is the decision rule and the traceability format. This skill **specifies** these
verifications; it does **not write** them — that is `eval-author`'s job. The traceability
table is the handoff artifact.

> Only load this file when writing Section 8 (verification handoff).

## The core distinction: tests verify deterministic parts, evals verify the rest

The dividing line is whether the correct answer is **fixed and exactly checkable**:

- **Deterministic criterion → a TEST.** There is one right answer (or a finite known
  set), checkable by exact equality, a status code, a thrown error type, an invariant, or
  schema conformance. A unit or integration test asserts it and is expected to be green
  every run. Most ACs land here.
- **Non-deterministic / judgment criterion → an EVAL.** The output is open-ended and
  there is no single correct string — generated prose, a summary's faithfulness, a
  ranking's sensibility, a classification's quality, anything an LLM produces or judges.
  A hard equality assertion here is *flaky and wrong*; instead an **eval** scores the
  output against a **rubric** and passes at a **threshold** (e.g. ≥ 0.8 faithful across a
  labeled set). Evals tolerate variance by design.

The same feature often needs both: the *plumbing* around an LLM call (the request is
formed, a 200 is returned, the response is persisted) is deterministic → tests; the
*quality* of what the model produced is non-deterministic → an eval.

## The decision rule (per criterion)

For each AC-n / E-n, ask in order:

1. **Is the expected result a fixed value, status, error, or invariant?** → **test**
   (pick unit vs integration by whether real dependencies must participate).
2. **Does correctness depend on judging open-ended output for quality/faithfulness/
   ranking?** → **eval** (name the rubric dimension and a threshold).
3. **Both?** → split it: a test for the deterministic envelope + an eval for the
   judgment. (This usually means the AC wasn't atomic — consider splitting it in
   Section 5.)
4. **Neither — you can't say how it'd be verified at all?** → the criterion is not yet
   checkable. Step 3 (acceptance criteria) failed for it: rewrite it until it is, or move
   it to Open questions. **An unverifiable criterion does not ship in the spec.**

## Choosing the test altitude (when it's a test)

- **Unit** — pure logic, a transform, a validator, a boundary calculation. Fast, no I/O.
- **Integration** — the criterion spans a real boundary (DB, queue, HTTP, auth) and a
  mock would fake the very thing under test. Most behavioral ACs (Given/When/Then) are
  integration-shaped.
- **Property/invariant** — a `base` invariant AC ("never creates or destroys money",
  "soft-deleted never appears in results") maps to a property-based test or a broad
  assertion, not a single example.

## Specifying an eval (when it's an eval)

Hand `eval-author` enough to build it — name, don't write:

- **What's judged:** the property (faithfulness, relevance, format-adherence, harm-
  absence, ranking quality).
- **Rubric dimension(s):** the scale the judge applies (e.g. 0–1 faithfulness: does every
  claim trace to the source?).
- **Threshold + dataset shape:** the pass bar and roughly what the labeled/golden set
  covers (happy path + the edge cases from Section 6 that are judgment-shaped).
- **Why an eval, not a test:** one line — "output is free-text; exact match would be
  flaky".

## The traceability table (the handoff artifact)

Every AC and every defined edge case appears exactly once. Coverage is the gate: a row
with no instrument is a hole in the contract.

| Criterion | Verify with | Instrument | Note / rubric |
|-----------|-------------|------------|---------------|
| AC-1 | test | integration | happy-path share-link creation |
| AC-2 | test | unit | date parse, parametrized from the table |
| AC-3 | test | property/invariant | conservation invariant |
| AC-4 | test | unit | empty-input boundary (E-1) |
| AC-5 | test | integration | non-owner → 403, no write (E-2) |
| AC-7 | eval | rubric, threshold ≥ 0.8 | summary faithfulness — output is free-text |

Rules for the table:
- **One row per AC and per defined edge case** — full coverage, no gaps.
- **Reference the edge-case row** (E-n) a test covers, so the sweep in Section 6 is
  traceably verified, not just listed.
- If a feature has **zero** judgment criteria, say so explicitly ("no evals — all criteria
  are deterministic") rather than leaving the eval column empty and ambiguous.

## The boundary with `eval-author`

This skill stops at the **table + eval specs**. `eval-author` takes the handoff and
writes the actual tests, the rubrics, the golden datasets, and wires them into the
project's suite. If the user asks you to *write* the tests/evals now, that is the
`eval-author` skill — hand off the table and redirect; do not start authoring tests here.
