# Edge-case checklist — the dimensions to sweep

Edge cases are where under-specified features fail in production, and they are exactly
the decisions an agent will make *silently* if the spec doesn't make them *explicitly*.
Sweep these dimensions deliberately — do not free-associate. For each dimension that
**applies** to this feature, decide the behavior and write it as an assertion (an AC or
an E-row with defined behavior); for each that applies but you can't decide, move it to
**Open questions**. A dimension that genuinely doesn't apply is fine to skip — but skip
it *consciously*, not by forgetting.

> Only load this file when enumerating Section 6 (edge cases). The goal is to surface
> implicit decisions, not to list every theoretical input.

## The dimensions

### 1. Empty / null / missing
- Empty collection, empty string, zero rows, no results.
- Null / None / undefined / absent optional field.
- Missing required field; missing auth token; missing config.
- *Decide:* is empty a valid success (return `[]`/`{}`) or an error? They are different
  contracts — pick one.

### 2. Boundary & off-by-one
- Min and max of every range (0, 1, n, n+1; first/last; inclusive vs exclusive).
- Exactly-at-the-limit (the 30-day boundary, the 100-char limit, the quota edge).
- Pagination edges: first page, last page, page past the end, page size 0.
- Time boundaries: midnight, DST shift, leap day, epoch, far-future dates.

### 3. Size & overflow
- Oversize input (huge payload, 10k-item list, multi-MB string).
- Numeric overflow / precision loss; very large or very small numbers.
- Unbounded growth (does anything accumulate without a cap?).
- *Decide:* the limit and the over-limit behavior (reject with 413? truncate? paginate?).

### 4. Malformed / wrong-type / encoding
- Wrong type (string where number expected), wrong shape, extra/unknown fields.
- Malformed structure (broken JSON, invalid UTF-8, injection-shaped strings).
- Unicode, emoji, RTL, whitespace-only, leading/trailing whitespace, case.
- *Decide:* reject (strict) vs coerce (lenient) — and say which, because silent coercion
  corrupts downstream state.

### 5. Duplicate / replay / idempotency
- The same request twice (double-click, retry, at-least-once delivery).
- Duplicate key / unique-constraint collision.
- *Decide:* is the operation idempotent? What does the second call return — same result,
  409, or a no-op?

### 6. Concurrency & ordering
- Two writers racing the same record (lost update? last-write-wins? optimistic lock?).
- Out-of-order events / messages; a read between two writes.
- Re-entrancy; a long operation overlapping its own next invocation.
- Partial visibility (reader sees a half-applied change).

### 7. Permission / authentication / tenancy
- Unauthenticated caller; authenticated-but-unauthorized; expired/invalid token.
- Cross-tenant / cross-user access (caller requests another owner's resource).
- Privilege boundaries (can a normal user reach an admin path?).
- *Decide:* the exact failure (401 vs 403) and that **no state changes** on denial.

### 8. Failure / timeout / retry / partial
- A dependency is down, slow, or returns an error mid-operation.
- Timeout: what surfaces to the caller, and is partial work rolled back or left?
- Retry: is it safe (→ idempotency)? Backoff? A retry cap?
- Partial failure in a multi-step operation: all-or-nothing, or best-effort with a
  reported partial result? (Either is fine — but pick one and assert it.)
- *Decide:* the **error contract** for each — this is where silent degradation hides.

### 9. State & lifecycle
- First-run / cold-start / no-data-yet; the very first record.
- Already-done / repeated transition (delete an already-deleted thing; start a started
  job).
- Deprecated / migrated / legacy data created under an older shape.
- Teardown / cancellation mid-flight.

### 10. The explicitly-out cases
- Inputs/states the spec deliberately does **not** support — name them and their
  behavior (reject clearly vs undefined). An out-of-scope input that still reaches the
  code needs a defined rejection, even if the *feature* is a non-goal.

## How to record a swept case

Each applicable case becomes a row in the Section 6 table with a **defined behavior**
(itself a checkable assertion, eligible for the eval handoff):

> | E-2 | permission | non-owner attempts restore | 403, no state change (AC-5) |

If you sweep a dimension and find the behavior genuinely undecided, do **not** invent it
— record it in Open questions and tie it to the blocked criterion:

> **Q-3** — On a concurrent restore + purge at the 30-day boundary, which wins?
> (blocks: E-7)

A swept-but-undecided case surfaced as a question is a *success* of this step. A case
that was never considered is the failure mode this checklist exists to prevent.
