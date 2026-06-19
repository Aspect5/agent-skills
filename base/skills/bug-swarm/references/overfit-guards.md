# Overfit guards — the false-fix floor

A patch that makes only the repro pass is the single most common failure mode of
automated repair. These guards are **mandatory** before any candidate can win. The
governing principle: a fix must address the *bug class*, not memorize the *one input*.

Only load this file when running Step 5 (overfit guard) or judging candidates.

## Hard rejects (any one ⇒ disqualified)

Reject a candidate outright if it does any of the following to go green:

- **Special-cases the repro input.** Branches on the literal value(s) the repro uses
  (`if x == <the-repro-value>: ...`, a hardcoded expected output, a lookup keyed on the
  test's exact data).
- **Weakens an assertion.** Loosens, narrows, or deletes an existing assertion;
  changes `==` to `>=`/`in`; widens a tolerance; removes a field from an equality
  check.
- **Broadens error handling to hide the failure.** Wraps the failing path in a wider
  `try/except` / `catch`, swallows the exception, returns a default on error, or
  converts a raise into a silent log.
- **Disables the signal.** Comments out a check/validation, marks the test (or a
  related test) `skip`/`xfail`/`.only`/`.skip`, deletes a test, or lowers a coverage/
  lint threshold.
- **Edits the repro test to pass.** Touches the committed repro/sibling tests to make
  them green (the test is the oracle; the fix is in the code, not the test).
- **Leaves the contract half-fixed.** Patches the consumer but not the producer (or
  vice versa) so the underlying drift remains.
- **Goes out of scope.** Edits files outside the agent's assigned scope, or touches a
  migration / schema / auth / public-API contract without escalation.

## The adversarial sibling test (required)

Before a patch wins, exercise it against inputs it never saw:

1. Take the repro's bug class and generate **1–2 sibling cases** with *different*
   inputs that exercise the same root cause (another boundary value, another field,
   another ordering). These are written by the selector, not the fix agent — the fix
   agent must not see them.
2. Run them against the candidate. **The patch must pass the siblings too.** A patch
   that passes the repro but fails a sibling is overfit — reject it.
3. Keep the surviving sibling tests; ship them alongside the repro as part of the
   regression net.

## Consensus-overfit catch (LLM-judge fix-spec)

When several agents converge on the *same* special-case, naive voting picks the wrong
fix. Add a fix-spec judge step: independently describe what a *correct* fix should do
(in terms of the root cause, not the inputs), then score each candidate against that
spec. A candidate that matches the inputs but not the spec loses to one that matches
the spec — even if more agents produced the former.

## Accept bar (all required)

A candidate is eligible to win only if **all** hold:

- Repro test passes; full regression suite is green.
- All adversarial sibling tests pass.
- No assertion weakened, no check removed, no test skipped/deleted to go green.
- Diff is scope-local; no migration/schema/auth/public-API contract changed without
  escalation.
- No new lint or type errors.
- The shipped repro + sibling tests **fail on the buggy code and pass on the fix**
  (verify by reverting the fix and re-running, if cheap) — a real tripwire, not
  vacuous coverage.

If no candidate clears this bar, **abstain** (Workflow Step 6) — ship the diagnosis,
not a guess.
