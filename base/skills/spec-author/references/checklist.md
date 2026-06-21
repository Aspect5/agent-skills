# spec-author base checklist (stable `base:<id>` ids)

The stable-id contract for this skill. Every `base:<id>` referenced in `SKILL.md` is
defined here, and a project profile rebinds or disables checks **by id**:

- `## OVERRIDE` → `base:<id> → <new rule>` rebinds a check (e.g. fix the acceptance
  form to Gherkin, mandate a "Privacy & data" section).
- `## SUPPRESS` → `base:<id>` turns a check off for that project.
- `## ADD` → appends project-specific checks (give them project ids, not `base:`).

The ids are the contract surface — **do not renumber them**; profiles depend on them.

> Only load this file when you need the id contract (Step 0 directive resolution and the
> Step 9 gate).

## Problem & scope

- **base:problem-before-solution** — The spec opens with the *problem* (who hurts, what
  the current behavior costs, what observable thing changes when done) **before** any
  proposed solution, and the raw request is quoted so the spec is traceable. A request
  phrased as a solution is reverse-engineered to its problem.
- **base:explicit-non-goals** — A Non-goals section is present and **never empty**: what
  the spec deliberately does *not* cover, each with a one-line reason. An empty Non-goals
  is a failed scope, not a clean one.
- **base:no-solutioneering** — The spec stays at the *what / why* layer. Hard constraints
  the solution must honor (a required API, a latency budget, a compliance rule, an
  existing schema) are recorded; the *how* (internal data structures, algorithms, file
  layout) is **not** dictated unless the user fixed it as a constraint. A "which of
  several options" question is redirected to `design-tradeoff`, not decided here.

  **Trip-wire — a leaked `how` forces one of three moves:**

  | Leaked "how" in the request | Ask / classify | Where it goes |
  |---|---|---|
  | "must use Redis" because a shared cache already standardizes on it | hard compatibility constraint | record in Constraints (§4) |
  | "use Redis" with no forcing reason — one cache among several | a design choice, not a requirement | redirect to `design-tradeoff` |
  | "store it in a `sessions` table with these columns" | implementation detail | drop it; the AC names the observable behavior, not the schema |

  If you cannot tell which row applies, that is an **open question**, not a default.

## Acceptance criteria

- **base:acceptance-testable** — Every acceptance criterion is a single **checkable
  assertion**: atomic (one assertion each), observable (an output / state change / status
  code / event / user-visible effect, never an internal step), unambiguous (no
  "fast / robust / user-friendly" without a number or concrete predicate), and numbered
  (AC-n). Non-functional asks get a budget or a named standard or they are not criteria.
  Profiles may pin the surface form via `acceptance_style` (OVERRIDE this).

## Edge cases

- **base:edge-cases-enumerated** — The edge-case dimensions in
  `edge-case-checklist.md` were swept; every applicable case has a **defined behavior**
  (stated as an assertion) **or** is explicitly listed as an open question. Edge cases are
  enumerated by dimension, not free-associated.

## Interface / contract

- **base:interface-contract** — The boundary the feature exposes or consumes is sketched:
  signature / endpoint / event / schema with inputs (types, required/optional), the
  success output shape, and the **error contract** (which failures surface how). If an
  existing contract changes, **every consumer / both sides** is named and the change is
  marked additive vs breaking. This is a contract sketch, not an implementation.

## Verification handoff

- **base:spec-to-eval-handoff** — Every acceptance criterion and defined edge case maps
  to a future verification in a traceability table: **deterministic → a test**,
  **non-deterministic / judgment → an eval** (with rubric + threshold). No criterion is
  left unverifiable. The skill specifies these and hands the table to `eval-author`; it
  does not write them.

## Honesty & process

- **base:open-questions-surfaced** — Unresolved decisions (ambiguous intent, an edge case
  with no decided behavior, an unconfirmed constraint) are collected in an **Open
  questions** section and asked about — never silently guessed and buried in confident
  prose.
- **base:output-discipline** — The full spec is written to `spec-<slug>.md`
  incrementally; inline output is a tight summary + path only.
- **base:approval-before-write** — No `git add` / commit / branch / push, and no
  overwrite of an unnamed existing spec, without an explicit approval pause; default is to
  leave the spec uncommitted for review.
- **base:fan-out-gated** — Any multi-agent fan-out (sub-specs of a large initiative) ran a
  cost preflight, honored the `fan_out` knob, and capped at one agent per genuinely
  independent sub-surface.
- **base:no-implementation** — The skill stops at the spec. It does not implement, does
  not write the tests/evals (→ `eval-author`), and does not choose the architecture
  (→ `design-tradeoff`).
