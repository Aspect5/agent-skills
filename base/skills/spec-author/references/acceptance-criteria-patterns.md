# Acceptance-criteria patterns — turning prose into checkable assertions

The single move that makes a spec executable: every requirement becomes an assertion a
test or a human can mark **true or false**. Prose hope ("it should feel fast", "handle
errors gracefully") is not a criterion — it is a place where the agent will guess. This
file is the conversion kit.

> Only load this file when writing or reviewing Section 5 (acceptance criteria).

## The bar a criterion must clear

A criterion is acceptance-ready only if it is all four:

1. **Atomic** — one assertion. Split conjunctions: "validates the input **and** saves
   **and** notifies" is three criteria, not one. A failing compound criterion can't tell
   you which clause broke.
2. **Observable** — phrased as an *output*: a return value, a state change, a status
   code, an emitted event, a persisted row, a user-visible effect. Never an internal
   step ("calls `normalize()`", "uses a queue") — the spec has no business naming the
   implementation, and an internal-step criterion can be satisfied while the behavior is
   still wrong.
3. **Unambiguous** — no weasel words without a predicate (see the rewrite table).
4. **Numbered** (AC-1, AC-2, …) so edge cases, the eval handoff, and review can reference
   it.

## Three forms — pick by the criterion's shape

### A. Given / When / Then — for behavioral criteria

The default for "when X happens, Y should result". Maps one-to-one to an integration
test.

```
AC-1 — Given <precondition / context / actor & permission>,
       when <the single action / trigger>,
       then <the single observable result>.
```

- Keep one trigger and one observable per criterion (atomicity).
- Put the actor and their permission in the *Given* — it forces the auth edge cases out
  into the open.
- Example: *Given a signed-in user who owns the document, when they request a share link,
  then a link scoped to that document is returned with a 24h expiry.*

### B. Input → expected-output table — for data / transform / validation criteria

When the behavior is "this input yields this output", a table is denser and more
complete than prose, and it doubles as the test's parametrized cases.

| AC | Input | Expected output |
|----|-------|-----------------|
| AC-2 | `"2026-06-20"` | `Date(2026, 6, 20)` |
| AC-3 | `""` (empty) | `ValidationError("date required")` |
| AC-4 | `"2026-13-01"` (bad month) | `ValidationError("invalid month")` |

The error rows are criteria too — an unspecified error path is where silent failures are
born.

### C. Invariant — for properties that must ALWAYS hold

For safety/consistency properties that aren't tied to one trigger. These often become
property-based tests or assertions, not example tests.

```
AC-5 — Invariant: total debited == total credited across any transfer (no money
       created or destroyed).
AC-6 — Invariant: a soft-deleted record never appears in any list/search result.
```

## Weasel word → predicate (the rewrite table)

Every word on the left is a hidden decision the agent will otherwise make for you.
Replace it with a number, a named standard, or a concrete predicate.

| Weasel phrasing | Rewritten as a checkable assertion |
|---|---|
| "fast" / "performant" | "p95 response < 300 ms at 50 rps" |
| "handles errors gracefully" | "on backend timeout, returns 503 with `Retry-After`; no partial write persists" |
| "robust to bad input" | enumerate the inputs (→ table form B) and the defined output for each |
| "scales" | "serves 10k concurrent sessions with no error-rate regression" (or → a non-goal if untested) |
| "secure" | name the standard/control: "all endpoints require a valid session; IDs are ownership-checked server-side" |
| "user-friendly" / "intuitive" | a concrete observable: "the error message names the offending field" — or move to a design task, not an AC |
| "accessible" | "meets WCAG 2.1 AA for the new controls: keyboard-navigable, labeled, 4.5:1 contrast" |
| "most cases" / "usually" | define the case split explicitly; "usually" hides an unspecified branch |
| "etc." / "and so on" | enumerate the list — "etc." is an unwritten requirement |
| "should probably" | decide: it is a criterion (then assert it) or it is not (then drop it or → Open questions) |

## Non-functional criteria are still criteria

Performance, security, accessibility, and reliability asks get the *same* treatment:
attach a **budget** (a number) or a **named standard**, with the conditions under which
it's measured. "Fast under load" with no number and no load definition is not an
acceptance criterion — it is an open question. If a non-functional property genuinely
cannot be pinned yet, move it to Open questions rather than letting it masquerade as a
criterion.

## Anti-patterns (reject these in self-check)

- **Implementation-coupled:** "AC: uses Redis for the cache." That is a *how* (or a
  constraint) — not an observable acceptance result.
- **Untestable mood:** "AC: the experience feels polished." No true/false — drop or
  concretize.
- **Compound:** "AC: validates, saves, and emails the user." Split into three.
- **Tautological:** "AC: the function works correctly." Says nothing checkable.
- **Internal-step:** "AC: the handler calls the validator first." The order of internal
  calls is not the contract; the rejected-bad-input *result* is.
