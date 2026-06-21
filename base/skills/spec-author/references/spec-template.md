# Spec template — the deliverable structure

The structure every spec follows, in order. Discover a project's own template first
(profile `spec_template`, then a `*spec*.md` / `*.feature` / RFC template in
`docs/specs/`, `docs/rfcs/`); fall back to this MADR-style default and **state in the
spec that you fell back** because no project convention was found. Keep the spec under
~500 lines — a spec nobody reads is not a contract.

> Only load this file when you are structuring or writing the spec document.

## Section order

```markdown
# Spec: <feature name>

> Status: draft · Author: <you/agent> · Date: <date> · Source: <ticket/PR/message link>

## 1. Request (verbatim)

> "<the raw ask, quoted exactly — never paraphrased away>"

## 2. Problem statement (the why, before any solution)

<Who hurts today, what the current behavior costs them, and what observable thing is
different when this is done. One or two tight paragraphs. NO proposed solution here.>

## 3. Goals & non-goals

**Goals (in scope)**
- <bounded behavior 1>
- <bounded behavior 2>

**Non-goals (out of scope — never empty)**
- <thing deliberately not covered> — <one-line reason>
- <thing deliberately not covered> — <one-line reason>

## 4. Constraints

<Hard constraints the solution MUST honor — a required API to stay compatible with, a
latency/cost budget, a compliance rule, an existing schema not to break. These are
part of the *what*. Do NOT list internal data structures / algorithms unless the user
fixed them. If a constraint is really "one option among several", redirect it to
design-tradeoff and note that here.>

## 5. Acceptance criteria

<Each a single checkable assertion, numbered. See acceptance-criteria-patterns.md.>

- **AC-1** — Given <context>, when <action>, then <observable result>.
- **AC-2** — <input> → <expected output>.  (table form for data/transform criteria)
- **AC-3** — Invariant: <property that must always hold>.

## 6. Edge cases

<Swept by dimension from edge-case-checklist.md. Each with a DEFINED behavior, or
moved to Open questions.>

| # | Dimension | Case | Defined behavior |
|---|-----------|------|------------------|
| E-1 | empty/null | input list is empty | return `[]`, status 200 (AC-4) |
| E-2 | permission | caller is not the owner | 403, no state change (AC-5) |
| E-3 | concurrency | two saves race | last-write-wins, no partial record (AC-6) |

## 7. Interface / contract sketch

<The boundary shape only — inputs/outputs/error contract. NOT the implementation.>

- **Signature/endpoint/event:** <name + method/path/topic>
- **Inputs:** <field: type, required|optional, validation>
- **Output (success):** <shape + status>
- **Error contract:** <failure → surfaced-as: status/error-type/message>
- **Compatibility:** <additive | breaking; if breaking, the consumers affected and the
  migration/version note>

## 8. Verification handoff (spec → eval)

<Traceability table: every AC and defined edge case → a test or an eval. See
eval-handoff.md. This skill specifies these; eval-author writes them.>

| Criterion | Verify with | Instrument | Note |
|-----------|-------------|------------|------|
| AC-1 | test | integration | happy path |
| AC-4 | test | unit | empty-input boundary |
| AC-7 | eval | rubric, threshold ≥ 0.8 | summary faithfulness (non-deterministic) |

## 9. Open questions

<Unresolved decisions surfaced for the user — ambiguous intent, an undecided edge case,
an unconfirmed constraint. NEVER guess these silently. Empty is fine ONLY if truly none
remain.>

- **Q-1** — <question> (blocks: AC-n / E-n)
```

## Worked mini-example (the shape, compressed)

> **Request:** "Add a way to undo deleting a note."
>
> **Problem:** Users who delete a note by mistake have no recovery; support tickets
> for "I lost my note" are the #2 contact reason this quarter. Done = an accidental
> delete is recoverable for a bounded window without contacting support.
>
> **Goals:** soft-delete on the existing delete action; a time-boxed restore path.
> **Non-goals:** version history / per-edit undo (separate spec); cross-device sync of
> the trash (infra owns sync); admin bulk-restore (no demand yet).
>
> **AC-1** — Given a note the user owns, when they delete it, then it is marked
> `deleted_at` (soft) and excluded from list/search results.
> **AC-2** — Given a note deleted < 30 days ago, when the user restores it, then it
> reappears in all lists with its original content and `deleted_at` cleared.
> **AC-3** — Invariant: a note older than 30 days in `deleted` state is purged and is
> not restorable.
>
> **E-1** (permission) — non-owner attempts restore → 403, no change (AC-4).
> **E-2** (concurrency) — restore + hard-purge race at the 30-day boundary → purge
> wins, restore returns 410 (AC-5).
>
> **Contract:** `POST /notes/{id}/restore` → 200 `{note}` | 403 | 404 | 410. Additive;
> existing `DELETE /notes/{id}` becomes soft (callers reading `deleted_at` unaffected).
>
> **Handoff:** AC-1,2,3,4,5 → integration tests; no judgment criteria → no evals.

The example is deliberately small; real specs carry more edge cases and a fuller
contract, but the *shape* — problem→scope→criteria→edges→contract→handoff — is fixed.
