# Whole-repo audit report template (opt-in swarm)

Use only when SKILL.md Step 8 fired (explicit "de-slop the whole repo" + `fan_out` allows
it). Write the **full** report to a file (e.g. `simplify-audit.md`) incrementally; emit only
a tight summary inline (top kill-list items, top complexity offenders, total estimated LOC
removable). This protects the output budget on large codebases.

Only load this file when running the swarm.

## Read-only investigation tracks (sub-agents never write)

Split into independent read-only tracks; each returns evidence-backed findings; the main
agent synthesizes and is the only writer (Steps 6–7). Typical tracks:

1. **Backend dead code** — unused imports, orphan files, dropped-migration references still
   in code, routes with zero consumers, pass-through shims.
2. **Frontend dead code** — unused components/hooks/utils, dead exports, stale tests whose
   source is gone, unused runtime dependencies (exclude build/config tooling).
3. **God files & complexity** — files over the size thresholds, longest functions, high
   import counts, concrete split proposals.
4. **Duplication & patterns** — near-duplicate services/helpers, inconsistent
   class-vs-function or error/logging patterns, config/constant sprawl, stale docs.
5. **Dependency modernization** — deprecated library APIs vs current idioms (only flag with
   a concrete current-vs-modern pair).

Each track prompt must state: READ-ONLY; evidence required per finding (grep output / line
counts / import chains); respect intentional architecture from CLAUDE.md/AGENTS.md.

## Report structure

```
# Simplify Audit — <repo> (<date-agnostic: omit dates>)

## 1. Immediate kill list (provably dead — clears all four safe-deletion gates)
- [ ] `path/file.py` — orphan, 0 callers, no dynamic/config entry (evidence: …)
Estimated removable: ~N lines.

## 2. Top complexity offenders (ranked by line_count × import_count)
| Rank | File | Lines | Imports | Score | Primary issue |
|------|------|-------|---------|-------|---------------|

## 3. Duplication & consolidation
Current state → proposed single source of truth → estimated LOC reduction. Note any
contract that must be migrated on both sides.

## 4. If starting over (redo lens)
The cleaner shape the team would choose now, and whether migrating toward it is worth it.

## 5. Modernization opportunities
| Library | Current pattern | Modern alternative | Risk |

## 6. Recommended sequence (safety first, then impact/effort, then independence)
- Wave 1 — safe deletions (kill list; zero behavior change)
- Wave 2 — straightforward simplifications (inline wrappers, modernization, helper extracts)
- Wave 3 — structural refactors (need behavior anchor + review): consolidations, god-file splits

## 7. Advisory / needs-human
Items that failed a safe-deletion gate or need product/migration judgment.
```

## Synthesis rules

- **Cross-reference** tracks: an orphan file that's also a god file is a strong delete signal.
- **Quantify**: "47 unused imports across 12 files, ~200 lines removable", not "lots of dead
  code".
- **Kill list = only provably-dead items** (all four gates). Everything uncertain goes to
  §7 advisory, never the kill list.
- **Prioritize by developer impact** — surface the 1500-line god file before 50 trivial
  imports.
- The audit is **advisory by default**: it produces the plan. Applying it runs back through
  SKILL.md Steps 6–7 (behavior anchor, safe-deletion bar, project gate, human-approval pause
  for destructive steps).
