# AI-smell signatures (detect by structure, not feel)

LLM-generated code has recognizable failure shapes. Flag a smell only when its **structural
signature** is present AND you can produce the required evidence — never on vibe. Each row
maps a smell to what it looks like and the proof you must attach before reporting it.

Only load this file when hunting for candidates (SKILL.md Step 5).

| Smell | Structural signature | Required evidence | Default action |
|---|---|---|---|
| **Over-abstraction** | Factory / registry / strategy / `*Manager` / `*Provider` / hook with exactly one concrete implementation or one call site; an interface with a single implementer; a builder for a 2-field object. | grep showing 1 caller / 1 implementer; the abstraction adds no branching, policy, or substitution point. | Inline it; collapse to the direct call. Clears `base:over-generalization`. |
| **isX-flag mega-component** | One function/component taking many boolean/mode flags (`isEditing`, `isCompact`, `variant`) that fork into near-disjoint bodies. | Count of mode flags; the disjoint branches share little logic. | Split into focused units per real mode; delete dead modes (after safe-deletion bar). |
| **Context-blind duplication** | Same transform/validator/mapper/error-handling copied across files because the model couldn't see the existing helper. | ≥2 `file:line` sites with near-identical logic; the canonical helper exists or is worth extracting. | Consolidate to one source of truth. Watch `base:both-sides-of-contract` if it's a shared format. |
| **Hallucinated / removed API** | Calls to a method/field/endpoint that does not exist, or one removed by a recent migration but still referenced. | grep proving the symbol is undefined / was dropped (cite the migration); a failing import/type check. | Fix to the real API or delete the dead reference. This is a correctness bug surfaced by cleanup — fix, don't just note. |
| **Hidden coupling / circular deps** | Modules that import each other transitively; a "util" that reaches back into a feature module; global mutable state threaded through "helpers". | The import cycle / back-reference chain (`a → b → a`); the shared mutable symbol. | Propose a dependency-direction fix (extract the shared piece, invert the import). Usually advisory + a proposal, not an in-pass rewrite. |
| **Defensive fog** | `try/except: pass`, broad `except Exception`, `?? default` / `|| {}` swallowing real errors, `if not X: return <empty>` compat shims, "backward compat" branches with no proven legacy caller. | grep for the legacy caller returning zero; the swallowed-error path; no test exercising the fallback. | Remove the dead compat path / surface the real error. Clears `base:defensive-fog`; respect `base:no-papered-fallback`. |
| **Tangled refactor + feature** | A single commit/diff mixing a behavior change with a rename/move/restructure, hiding the real change. | `git show`/`git diff` showing both a logic change and a structural change interleaved. | Do not replicate the anti-pattern: keep cleanup separate from any behavior change (`base:no-tangled-commits`). |
| **AI prose/code bloat** | Comments restating the next line; docstrings narrating obvious control flow; theatrical names (`process_everything`, `ComprehensiveHandler`); "future-proofing" config/params never read; scaffolding far larger than the need. | The redundant comment/name/param; grep showing the config/param is never read. | Trim comments, rename to plain, delete unread params. Clears `base:ai-prose-bloat`. |
| **One-true-config sprawl** | The same magic value (timeout, limit, URL) hardcoded in 3+ places; a config object with many keys, most unused. | ≥3 `file:line` sites of the literal; grep showing unused keys read nowhere. | Centralize the genuinely-shared value; delete unused keys. Avoid over-DRYing coincidental matches. |

## Guardrails when acting on a smell

- A smell is a **hypothesis**, not a verdict. Confirm with the required evidence; if you
  cannot, it stays an advisory note, not an edit.
- Over-abstraction and duplication often interact: do not "fix" duplication by inventing a
  premature abstraction — prefer one direct shared function over a new framework.
- Hidden-coupling and god-file fixes are usually **proposals**, not in-pass rewrites, unless
  the unit is small, low-coupling, fully understood, and the behavior anchor covers it.
- Every action still passes through `base:safe-deletion-bar` (for removals) and
  `base:behavior-anchor` (green before and after).
