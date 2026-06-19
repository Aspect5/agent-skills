# ADR discovery, format, and templates

The deliverable is an Architecture Decision Record in **the project's own
format**. Discover it; do not assume. Write the record to a file (output
discipline) and keep it under ~500 lines.

> Only load this file for Step 8.

## Discovery precedence (last match wins)

1. **Profile pin** — `adr_dir` / `adr_template` in
   `.agents/profiles/design-tradeoff.md`. Use them verbatim.
2. **Existing ADR directory** — `docs/adr/`, `docs/decisions/`,
   `doc/adr/`, `architecture/decisions/`, or `adr/`. If one exists:
   - **Match its numbering** (`0001-…`, `NNNN-…`, or date-prefixed
     `YYYY-MM-DD-…` — copy whatever the newest few files use). Find the next
     number/date by listing the directory; do not guess.
   - **Match its template** — open the two most recent records and mirror their
     section headings exactly (Status / Context / Decision / Consequences is the
     classic shape, but use whatever the repo actually uses).
3. **Template file in those dirs** — a `*template*.md` or `0000-template.md`.
   Copy it and fill it in.
4. **Inline ADRs** — some repos keep decisions in `ARCHITECTURE.md` or a single
   `DECISIONS.md`. If that's the convention, append there in the same style
   rather than creating a new file.
5. **Fallback: MADR-minimal** (below). When you fall back, **state in the record
   and in your summary that no project ADR convention was found** so the user can
   point you at the right one.

Resolve the slug from the decision (kebab-case, ≤6 words). Filename follows the
discovered scheme, e.g. `docs/adr/0042-event-bus-vs-direct-rpc.md` or
`docs/decisions/2026-06-19-shard-by-tenant.md`.

## MADR-minimal fallback template

Use only when discovery finds no project convention. MADR (Markdown Any Decision
Record) is the widely-adopted lightweight standard.

```markdown
# <NNNN or DATE>. <Decision title in one line>

- Status: proposed            # proposed | accepted | superseded by <link> | deprecated
- Date: <YYYY-MM-DD>
- Deciders: <names / "pending">
- Reversibility: <two-way door | one-way door>

## Context and problem statement

<2–5 sentences: what forces this decision now, and the constraints. State the
prioritized quality attributes and their weights.>

## Decision drivers (hard constraints)

- <constraint 1 — must hold for any option>
- <constraint 2>

## Considered options

1. **<Option A name>** — <one line>
2. **<Option B name>** — <one line>
3. **<Option C name>** — <one line>

## Decision matrix

| Attribute (weight) | Option A | Option B | Option C |
|---|---|---|---|
| Correctness (5) | 4 — <why> | 3 — <why> | 5 — <why> |
| … | … | … | … |
| **Weighted total** | … | … | … |

## Diagrams

```mermaid
graph LR
  <per-option or comparative flow>
```

## Sensitivity & tradeoff points  <!-- one-way doors -->

- **Tradeoff:** <improving X degrades Y>.
- **Sensitivity:** if <assumption> is false, the recommendation flips to <option>.

## Decision

<The chosen option, tied to the dominant attributes.>

## Consequences

- **We gain:** <…>
- **We give up:** <the honest downside>
- **Revisit if:** <flip condition / threshold>
- **Back-out path:** <how to reverse or contain if wrong>
- **Fitness function:** <a test/metric/lint that fails on drift, if feasible>

## Review findings  <!-- if a stress-test pass ran -->

<Material critiques folded in; what changed as a result.>
```

## Status field discipline

- Default `Status: proposed`. Do **not** set `accepted` on the user's behalf —
  the decision is theirs to ratify.
- If this record supersedes an existing ADR, set the old one's status to
  `superseded by <link>` only after asking.

## Common pitfalls

- **Inventing a numbering scheme** when the repo already has one → mismatched
  files. List the directory first.
- **A "Review findings" appendix that contradicts the body** → fold critiques into
  the relevant sections; the body must be internally consistent.
- **Committing the record automatically** → human-approval pause first (Step 8);
  default to leaving it uncommitted.
