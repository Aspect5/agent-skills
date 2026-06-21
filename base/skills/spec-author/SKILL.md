---
name: spec-author
description: >-
  Turns a fuzzy feature request, idea, or ticket into a precise, testable
  specification an agent can build against without re-deriving intent: a
  problem statement (the why, before any solution), explicit scope and
  NON-goals, acceptance criteria written as checkable assertions, enumerated
  edge cases, interface/contract sketches, and an explicit criterion→eval
  handoff. Use when asked to write a spec, turn an idea / ticket / PRD into
  requirements or acceptance criteria, scope a feature before building, define
  "done", or "spec this out". Do not trigger for: choosing between competing
  architectures, data models, or a build-vs-buy / rewrite-vs-refactor call —
  deciding the HOW (use design-tradeoff); writing the tests, evals, rubrics, or
  datasets themselves (use eval-author — this skill specifies them and hands off);
  implementing an already-specified feature; reviewing a diff (use code-review);
  refreshing existing guidance docs or generating end-user / API reference docs
  (use docs-refresh); summarizing where a session stands or producing a
  resume / next-steps prompt for the next agent (use handoff); or general Q&A.
---

# Spec Author

## Overview

Specification is the bottleneck: an agent can only build what it can unambiguously
read, and most "the agent did the wrong thing" failures are really "the request was
under-specified" failures. This skill converts a fuzzy ask into a **precise, testable
specification** — the contract a downstream agent executes against without
re-guessing intent. The hard contract: every spec states **the problem before any
solution**, draws an explicit scope line with named **non-goals**, and renders each
acceptance criterion as a **checkable assertion** (a thing that can be observed true
or false), not as prose hope. The spec also enumerates the edge cases, sketches the
interface/contract, and hands every acceptance criterion off to a future test or eval.

This skill **ends at the spec**. It does not implement, it does not write the tests
or evals (it names them for `eval-author`), and it does not decide *which*
architecture to build (that is `design-tradeoff`). A spec that smuggles in an
implementation has skipped the one job it had: pin down *what* and *why* so the *how*
can be judged against it.

> Output discipline: write the spec to a file (`spec-<slug>.md`) **incrementally** as
> sections firm up, and emit only a tight inline summary (the one-line problem, the
> scope line, the criteria count, the path). Never paste the full spec back into the
> conversation — guard the output-token budget.

## Step 0 — Context-Absorption Prelude

Run this before anything else. Never fail for lack of a profile — the base runs
unmodified with zero config and better with one.

1. **Notice what's already in context.** `AGENTS.md` / `CLAUDE.md` (root and nested,
   path-scoped) are typically already loaded — use them for the project's domain
   vocabulary, existing contracts, and conventions so the spec speaks the codebase's
   language. Do not re-read blindly.
2. **Read the profile if present:** `.agents/profiles/spec-author.md`. If it exists,
   apply its frontmatter knobs (`model`, `budget`, `fan_out`, `focus_paths`,
   `ignore_paths`, plus any `spec_template`, `spec_dir`, `acceptance_style`) and its
   `## ADD` / `## OVERRIDE base:<id>` / `## SUPPRESS base:<id>` directives against the
   base checklist in `references/checklist.md`. A SUPPRESSed `base:<id>` is dropped; an
   OVERRIDDEN one uses the project's rebinding (e.g. a fixed Given/When/Then form, a
   mandatory "Privacy & data" section).
3. **Resolve specifics in precedence, first hit wins:** profile values → introspect the
   repo (existing `docs/specs/`, `docs/rfcs/`, `*spec*.md` / `*.feature` templates, the
   ticket/PRD the user linked, current interfaces/schemas the feature must fit) → **ask
   the user once** if a load-bearing fact is still unknown (the *intent*, not the
   implementation) → else fall back to the defaults in `references/spec-template.md`.
4. **Fall back to defaults** when no profile and no template exist. Never stall for lack
   of config.

Honor the budget posture from the start: `fan_out: never` ⇒ stay single-pass;
`fan_out: ask` ⇒ run the cost preflight before any multi-agent step; `model: gpt-5.4`
⇒ prefer the lower-freedom, template-anchored path (fill the structured template,
table-form criteria) over open-ended prose; `model: gpt-5.5` with headroom ⇒ more
latitude in framing and edge-case reasoning.

## Workflow

> **Only load the reference files you need**, and only as a step needs them:
> `references/spec-template.md` (the deliverable structure),
> `references/acceptance-criteria-patterns.md` (turning prose into assertions),
> `references/edge-case-checklist.md` (the dimensions to sweep),
> `references/eval-handoff.md` (criterion → test/eval mapping).

### 1. Capture the request verbatim, then find the problem behind it

- **Quote the raw ask** (the ticket / message / PRD line) so the spec is traceable to
  what was actually requested. Do not paraphrase it away.
- **Write the problem statement: the *why*, before any solution** (`base:problem-before-solution`).
  Who hurts today, what does the current behavior cost them, what observable thing
  changes when this is done. A request phrased as a solution ("add a retry button")
  must be reverse-engineered to its problem ("users lose work when a save fails
  silently") — the problem, not the proposed fix, is what the spec is accountable to.
- If the underlying intent is genuinely ambiguous — not the implementation, the *goal*
  — **ask the user once**, tightly. A spec built on a guessed goal is worse than no
  spec. Do not ask about *how* to build it; that is not yours to fix here.

### 2. Draw the scope line — in and explicitly OUT

- **In scope:** the bounded set of behaviors this spec covers, as a short list.
- **Non-goals (mandatory, never empty):** what this spec deliberately does *not* cover,
  each with a one-line reason (`base:explicit-non-goals`). Non-goals are the highest-
  leverage section: they stop an agent from gold-plating, prevent scope creep, and make
  the boundary reviewable. "Out of scope: offline mode (separate spec), i18n (no
  non-English users yet), rate-limit tuning (handled by infra)." If you cannot name a
  single non-goal, the scope is not yet understood — keep framing.
- **Constraints vs. solutioneering** (`base:no-solutioneering`): record hard
  constraints the solution must honor (a required API to stay compatible with, a
  latency budget, a compliance rule, an existing schema it must not break) — these are
  legitimately part of the *what*. Do **not** dictate the *how* (data structures,
  algorithms, file layout) unless the user fixed it as a constraint. If a "must use
  Redis" appears, confirm it is a real constraint, not a leaked implementation guess;
  if it is just one option among several, that is a `design-tradeoff` question, not a
  spec clause — redirect.

### 3. Write acceptance criteria as checkable assertions

Each acceptance criterion must be a **single observable, checkable assertion**
(`base:acceptance-testable`) — a statement a test or a human can mark true/false, not a
mood. Convert every prose requirement using the patterns in
`references/acceptance-criteria-patterns.md` (Given/When/Then for behavioral criteria;
input→expected-output table for data/transform criteria; an invariant for properties
that must always hold). Each criterion is:

- **Atomic** — one assertion per criterion (split "validates and saves and notifies"
  into three).
- **Observable** — phrased in terms of an output, a state change, a status code, an
  emitted event, or a user-visible effect — never an internal step ("calls the
  helper") the spec has no business naming.
- **Unambiguous** — no "fast", "robust", "user-friendly" without a number or a concrete
  predicate. "Robust" becomes "returns 503 with `Retry-After` on backend timeout, and
  the client retries up to 3× with backoff". Non-functional asks (perf, security,
  accessibility) get the same treatment: a budget or a named standard, or they are not
  acceptance criteria.
- **Numbered** (AC-1, AC-2, …) so they can be referenced by edge cases, by the eval
  handoff, and in review.

### 4. Enumerate edge cases — sweep the dimensions, don't free-associate

Walk `references/edge-case-checklist.md` and enumerate the cases that actually apply
(`base:edge-cases-enumerated`): empty / null / missing, boundary & off-by-one, oversize
/ overflow, malformed / wrong-type input, duplicate / replay / idempotency, concurrency
& ordering, permission / unauthenticated / cross-tenant, partial failure & timeout &
retry, and the explicitly-out cases. For each one that applies, state the **defined
behavior** (an assertion, like an AC) — an enumerated edge case with no defined behavior
is an open question, so route it: either decide it (and add an AC) or list it under
**Open questions** for the user. The point is not to list every theoretical input; it
is to make the implicit decisions explicit so the agent does not invent them silently.

### 5. Sketch the interface / contract

Pin the **shape of the boundary** the feature exposes or consumes (`base:interface-contract`),
at the altitude the change demands — enough to remove ambiguity, not a full design:

- The **signature / endpoint / event / schema**: name, inputs (with types &
  required/optional), outputs (success shape), and the **error contract** (which
  failures surface how — status codes, error types, messages).
- **Compatibility:** does this change an existing contract? If so, name every consumer
  the spec must stay compatible with, and whether the change is additive (safe) or
  breaking (needs a version/migration note). A one-sided contract change is the
  canonical missed regression — the spec must call out both sides.
- This is a **contract sketch, not an implementation**: data shapes and behavior at the
  boundary, yes; the internal algorithm, no.

### 6. Hand off to evals (the spec→eval bridge)

Map **every acceptance criterion and defined edge case to a future verification**
(`base:spec-to-eval-handoff`), using `references/eval-handoff.md`. The discipline that
makes a spec executable: for each AC-n, name **how it will be verified** and pick the
right instrument —

- **Deterministic criterion → a test.** Exact output, status code, invariant, schema
  conformance: a unit/integration test asserts it.
- **Non-deterministic / judgment criterion → an eval.** Quality of generated text, "is
  the summary faithful", ranking sensibility, an LLM-judged or rubric-scored property:
  an eval (with a rubric and a threshold) measures it, because a hard equality assertion
  would be flaky or wrong.

Produce a **traceability table** (AC-n → test|eval → fixture/rubric note). This skill
**does not write** those tests or evals — it specifies them and hands the table to
`eval-author`. Coverage is the gate: an acceptance criterion with no mapped verification
is an untestable criterion (Step 3 failed for it) — fix the criterion or it does not
ship in the spec.

### 7. Budget & fan-out posture (single-pass is the default)

A spec is judgment-heavy and usually one focused pass — **single-agent, single-pass is
the default and needs no preflight.** Fan-out is rarely warranted here. If, and only if,
the request is a large multi-surface initiative that genuinely decomposes into
independent sub-specs:

- **Run a cost preflight first** and honor `fan_out`: `never` ⇒ stay single-pass and
  write the sub-specs sequentially; `ask` ⇒ state "this is ~N subagents, one per
  sub-surface — proceed?" and wait; `allowed` ⇒ proceed and announce the count.
- Honor `budget` and `model`: on `gpt-5.4` or a tight budget, prefer the lean
  single-pass template-fill; on `gpt-5.5` with headroom, more latitude is fine. Cap
  fan-out at one agent per genuinely-independent sub-surface; merge their sub-specs
  under one parent problem statement and one scope line.

### 8. Human-approval pause before any write outside the spec file

This skill **produces a document**; it does not mutate the codebase. Writing/overwriting
the spec file itself is the expected deliverable. But **before any** `git add` /
commit / branch / push, or before overwriting an existing spec the user did not name —
**stop and ask**. Default to leaving the spec uncommitted for review. Never push to a
protected branch on your own. For any emitted command, use shell-safe construction:
single-quote or heredoc messages (backticks run command substitution on zsh), check
exit codes directly, never pipe-mask an exit code.

### 9. Self-check / quality gate (final word)

Before presenting, verify every box — report the **literal** result, do not assert.
Every `base:<id>` the spec used (minus any SUPPRESSed by the profile) must be honored:

- [ ] **`base:problem-before-solution`** — the problem statement states the *why* and
      precedes any proposed solution; the raw request is quoted and traceable.
- [ ] **`base:explicit-non-goals`** — the Non-goals section is present and **non-empty**,
      each with a reason.
- [ ] **`base:no-solutioneering`** — the spec says *what/why*, not *how*; any `how` clause
      is a confirmed hard constraint, and any "which option" question was redirected to
      `design-tradeoff`, not decided here.
- [ ] **`base:acceptance-testable`** — every acceptance criterion is a single, atomic,
      observable, unambiguous, numbered assertion (no "fast/robust" without a predicate).
- [ ] **`base:edge-cases-enumerated`** — the edge-case dimensions were swept; each
      applicable case has a defined behavior **or** is listed as an open question.
- [ ] **`base:interface-contract`** — the boundary shape (inputs/outputs/error contract)
      is sketched; if an existing contract changes, both sides/consumers are named.
- [ ] **`base:spec-to-eval-handoff`** — every AC and defined edge case maps to a test
      **or** an eval in the traceability table; deterministic→test, judgment→eval; no
      criterion is left unverifiable.
- [ ] **`base:open-questions-surfaced`** — unresolved decisions are collected in an Open
      questions section, not silently guessed.
- [ ] **`base:no-implementation`** — the spec stops at the record; it does not contain or
      begin the implementation (that is a separate, handed-off task).
- [ ] **`base:output-discipline`** — the full spec is in `spec-<slug>.md`; only a tight
      summary went inline.
- [ ] **`base:fan-out-gated`** — any fan-out was cost-preflighted and honored `fan_out`.
- [ ] **`base:approval-before-write`** — no write/commit happened without the approval
      pause; commands are shell-safe.

If any box fails, fix it before presenting. Do not ship a spec on a partial gate.

Then present: a ≤6-sentence summary (the one-line problem, the scope line, the AC count,
how many map to tests vs evals, the path) and ask whether to refine the spec or hand it
to `eval-author` / implementation. Do not paste the full spec inline.

## Guardrails

- **Problem before solution, always.** If you cannot state the problem in one sentence,
  you do not yet have a spec — keep framing or ask. A solution looking for a problem is
  the most expensive thing an agent can build.
- **Non-goals are mandatory.** An empty Non-goals section is a failed scope, not a clean
  one.
- **Stay at the *what* layer.** Specify behavior and contracts; do not pick the
  architecture (→ `design-tradeoff`), do not write the tests/evals (→ `eval-author`), do
  not implement. Naming an internal helper or algorithm in a spec is a smell.
- **No untestable criteria.** A criterion that cannot be mapped to a test or eval is
  prose, not an acceptance criterion — rewrite it until it is checkable, or move it to
  Open questions.
- **Don't invent intent.** When the *goal* is ambiguous, ask once; never paper over a
  guessed goal with confident prose.
- **This skill never mutates the codebase** and never commits without the approval
  pause.

## References

Load only the reference files you need:

- `references/checklist.md` — the stable `base:<id>` checks profiles can
  OVERRIDE / SUPPRESS. The id contract surface — don't renumber.
- `references/spec-template.md` — the deliverable structure (every section, in order)
  plus a worked mini-example.
- `references/acceptance-criteria-patterns.md` — turning prose into checkable
  assertions: Given/When/Then, table form, invariants, and the "weasel-word → predicate"
  rewrites.
- `references/edge-case-checklist.md` — the dimensions to sweep (empty/null, boundary,
  malformed, concurrency, permission, failure/timeout, …) so edge cases are enumerated,
  not free-associated.
- `references/eval-handoff.md` — the criterion → test|eval decision rule and the
  traceability-table format that bridges the spec to `eval-author`.
