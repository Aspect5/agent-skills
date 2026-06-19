# Doc hierarchy, editing rubric, and templates

Load this when deciding **what goes where** and **how to phrase an edit**. It encodes the canonical-vs-pointer discipline and gives reusable shapes for the edit plan and the doc edits.

## The hierarchy (default; profile or repo pointer map overrides)

| Tier | Typical file(s) | Holds | Length posture |
|---|---|---|---|
| **Canonical** | `ARCHITECTURE.md` (or repo's stated canonical doc) | Deep structure: directory tree, routes, pipelines, data/contract shapes, deploy topology, schema/RLS, math/algorithms | As long as needed, but no duplication. The single source of structural truth. |
| **Pointer / agent-guidance** | `AGENTS.md`, `CLAUDE.md` | Workflow, commands, quality gates, hot-path/key-file map, conventions, and **pointers into the canonical doc** | Short. Optimized so a future agent actually reads it. Points at depth; never restates it. |
| **Onboarding / reference** | root `README.md`, `CONTRIBUTING.md`, `docs/`, ADRs | Setup, contribution flow, decision history | Scoped to their purpose. ADRs are append-mostly; don't rewrite a decided ADR — add a new one. |

**Resolve the real hierarchy first.** If the repo's own pointer map names a different canonical doc, that map wins over this default. Never impose this structure on a repo that organizes docs differently — refresh within the structure that exists.

## Routing rule (where a fact belongs)

- Structural / "how it's built" / contract shape → **canonical doc**.
- "How to run / test / deploy / what to edit" / convention → **pointer doc**, with a pointer to the canonical section for depth.
- A fact appearing in two tiers → keep it in the lower (deeper) tier and replace the upper copy with a one-line pointer. This satisfies `base:no-duplication` and `base:hierarchy-preserved`.

## Edit-plan entry template (write these to the plan file)

```
### <doc>:<section> — <verdict: stale | missing | misleading | accurate>
Claim (current text): "<quote or paraphrase the existing doc line>"
Evidence: <file:line | command + output | ADR ref>
Proposed edit: <exact replacement text, or "delete", or "add pointer to §X">
Target: <canonical | pointer> doc, section <name>
Confidence: <high | medium | low>   # low → list as open question, do not auto-apply
```

Stream entries into `docs-refresh-plan.md` as you find them. Inline, emit only counts-by-verdict + the top edits. This is the output-discipline guard — never paste the whole plan back.

## Phrasing rules for the doc text you write

- Imperative and durable. State the verifiable fact, not "recently changed to" (violates `base:no-time-sensitive`).
- Pointer phrasing: `See ARCHITECTURE.md §<n> "<heading>"` — and confirm that heading exists verbatim before writing it (`base:sections-match`).
- Preserve the surrounding doc's voice, formatting, and table/list conventions; a refresh should read as if the original author wrote it.
- When you remove a claim, prefer replacing it with the corrected one over leaving a gap; only delete outright when the whole subject is gone from the code.

## Validation snippets (run these in the validation step)

```bash
# Every referenced path resolves (collect paths from the diff, then):
git ls-files | grep -F "<path>"            # must hit for each documented path

# Every referenced symbol/command exists:
grep -rn "<symbol-or-script-name>" .       # confirm before keeping the reference

# Pointer-map headings match the canonical doc's real headings:
grep -n '^#' ARCHITECTURE.md               # compare against the pointers you wrote

# Re-review your own diff:
git diff --stat
git diff -- AGENTS.md CLAUDE.md ARCHITECTURE.md
```

A documented path/command/heading that does not resolve is a regression you just introduced — fix it before reporting done.
