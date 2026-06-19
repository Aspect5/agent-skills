---
name: simplify
description: >
  Behavior-preserving anti-slop cleanup pass on code, docs, or architecture: it removes
  needless complexity, dead code, duplication, and AI-shaped overengineering, then applies
  the smallest safe edits and verifies behavior is unchanged. Use when the user asks to
  simplify, de-slop, clean up AI-generated work, reduce overengineering, do a second
  architectural pass, ask "what would you do differently if redoing this", make code
  smaller or clearer, delete dead/duplicated code, or find refactor opportunities without
  changing product behavior. Do not trigger for: writing NEW features or net-new code,
  fixing a bug (use bug-swarm), reviewing a diff/PR for correctness before merge (use
  code-review), changing observable behavior on purpose, or general Q&A about the codebase.
---

# Simplify

Run a senior-engineer cleanup pass. Treat "simplify" as a review-plus-implementation
workflow: understand the intended design, find needless complexity with **evidence**,
then make the smallest safe changes that improve clarity, architecture, or
maintainability **without changing behavior**. On large codebases where correctness
matters, lean on deterministic guardrails (behavior anchors, the safe-deletion bar, the
project's own quality gate) over taste.

## Overview

The hard contract: **behavior is preserved.** A cleaner shape that changes any observable
behavior — an API response, a persisted format, an event, a UI state, a "bug" some caller
relies on — is a FAILURE, not a simplification. Everything below exists to make cleanup
safe: establish an anchor before editing, prefer deletion over abstraction, require proof
for every finding, and let the project's quality gate be the final word.

Default to the **leanest single-pass** path: investigate and apply locally in this one
agent. A multi-agent swarm (see Step 8) is an explicit opt-in for whole-repo audits only,
behind a cost preflight and the profile's `fan_out` setting.

## Step 0 — Context-Absorption Prelude

Run this before any analysis. Never fail for lack of a profile — absorb what exists, fall
back to sane defaults otherwise.

1. **Local guidance is already in context** — `AGENTS.md` / `CLAUDE.md` are auto-loaded by
   the harness. Skim them plus `ARCHITECTURE.md`, design docs, and ADRs for **intentional
   architecture** (hot/cold-state splits, bifurcated tooling, dual auth, deliberate
   indirection). Never flag a pattern the team chose on purpose. If the repo has a
   freshness/branch-sync rule, follow it before auditing.
2. **Read `.agents/profiles/simplify.md` if present.** Apply its frontmatter knobs
   (`model`, `budget`, `fan_out`, `severity_floor`, `focus_paths`, `ignore_paths`) and its
   `## ADD` / `## OVERRIDE base:<id>` / `## SUPPRESS base:<id>` sections against the
   checklist ids in `references/checklist.md`. Absent → use base defaults unchanged.
3. **Resolve commands** for the behavior anchor and quality gate (test / lint / typecheck /
   build), in precedence order: profile `commands` → introspect `package.json`,
   `pyproject.toml`, `Makefile`, `.github/workflows/*` → ask the user **once** if still
   ambiguous → otherwise note "no gate found" and rely on manual inspection.
4. **Calibrate freedom to the model.** `gpt-5.4`: lower freedom — prefer scripts, explicit
   checks, and conservative edits. `gpt-5.5`: more prose latitude for judgment calls. Either
   way, the safe-deletion bar and behavior anchor are non-negotiable.

## Workflow

1. **Scope the pass.**
   - User named files/dirs → inspect those plus their immediate callers and consumers.
   - User asked for a repo-wide sweep → inspect project docs, `git status`, recent commits,
     the file-tree shape, and high-churn areas; choose targets before editing. Consider the
     opt-in swarm (Step 8). Honor `focus_paths` / `ignore_paths`.
   - Exclude generated/vendored/lockfile/migration artifacts from "delete" candidates;
     migrations are append-only history, not slop.

2. **Build the architectural picture & behavior contract.**
   - Identify what MUST keep working: public APIs, persisted schemas, emitted events, UI
     states, background jobs, CLI surfaces, and the tests that pin them.
   - For any contract-format change, map **both producer and consumer sides** before
     touching it (`base:both-sides-of-contract`). Auditing only one side is the #1 way a
     "cleanup" silently breaks a consumer.
   - Separate intentional complexity from accidental complexity.

3. **Establish a behavior anchor BEFORE editing** (`base:behavior-anchor`).
   - Find or write a characterization / golden-master / snapshot test, or use an existing
     integration test, that pins current observable behavior — **including bugs-as-features**
     that callers depend on. The anchor must be **green before** you start.
   - If no anchor is feasible, lower your ambition: do only changes provable by static
     reasoning (e.g. removing a truly unreferenced symbol), and say so explicitly. Never
     do a risky refactor with no anchor.

4. **Run the redo lens.**
   - Ask: "If I were building this now with full current context, what would I do
     differently?" Identify the simpler target shape — fewer layers, clearer ownership,
     narrower contracts, smaller APIs, less state, more direct data flow.
   - Keep only differences that **materially reduce future maintenance cost**. Do not
     rewrite for aesthetic purity. Convert each insight into a safe patch, a small refactor
     proposal, or a note that the current shape is good enough.

5. **Hunt for simplification candidates — with evidence, not vibes.**
   - Detect AI-smell signatures by their structural signature, not feel — see
     `references/ai-smell-signatures.md` for the table of each smell and the evidence it
     requires (over-abstraction / one-caller factories, context-blind duplication,
     hallucinated or removed APIs, hidden coupling / circular deps, defensive fog, tangled
     refactor-plus-feature commits, AI prose/code bloat).
   - Standard targets: dead code (unused imports, exports, files, routes, flags, shims,
     deps), duplicate logic, over-generalization (factories/registries/config with one real
     use), defensive fog (silent fallbacks, broad excepts, compat paths with no proven
     legacy caller), god files, verbose comments restating code.
   - Every finding needs proof: a `file:line` reference, a grep showing zero callers, a line
     count, an import chain, a test, telemetry, or a project doc. "This feels bad" is not a
     finding; "this wrapper has one caller and adds no policy (foo.py:42)" is.

6. **Decide and apply — smallest safe changes first.**
   - **Before deleting anything, clear the four-gate safe-deletion bar** — load
     `references/safe-deletion-bar.md` for the gate definitions and the evidence template.
     All four gates must pass; if any is unmet → downgrade to an advisory finding, do not delete.
   - Implement safe wins directly: remove provably-dead code, inline pointless wrappers,
     collapse duplicate branches, simplify conditionals, narrow over-broad comments, reduce
     test over-specification.
   - **Incremental by default** (`base:incremental-strangler`): small steps with the anchor
     green between each. Big-bang only for a small, fully-understood, low-coupling unit.
   - **Human-approval pause** before any destructive or broad change: deleting files,
     removing a dependency, touching a public contract, or any edit outside the agreed scope.
     Present the plan, get a yes, then act. Reversible in-file simplifications inside the
     agreed scope don't need a separate pause.
   - For risky architectural changes, report a concise proposal first unless the user
     explicitly asked you to execute it. Do not bundle unrelated redesigns into one pass
     (`base:no-tangled-commits`).
   - Any new safety-net test you add must **fail on the bug/regression and pass on the fix** —
     not vacuous coverage that passes either way.

7. **Verify — the project's own gate is the final word.**
   - Re-run the behavior anchor: it must be **green after**, equivalent to before. Snapshots
     and contracts must stay equivalent, or affected callers must be audited.
   - Run the resolved quality gate (test / typecheck / lint / build) scoped to the changed
     surface, then the full gate if the change is non-trivial. **Report the literal pass
     line** (e.g. `pytest … 1185 passed`). Never pipe a gate command into `tail`/`head` —
     that masks its exit code; check the command's own exit status.
   - If no gate exists, state exactly what was manually inspected and what risk remains.
   - **Shell safety:** single-quote or heredoc any commit message (backticks trigger command
     substitution on zsh and silently blank words); check exit codes directly.

8. **(Opt-in) Whole-codebase swarm — budget-gated.**
   - Only for explicit "de-slop the whole repo" requests, and only if the profile allows it.
   - **Cost preflight:** announce "this fans out to ~N read-only sub-agents — proceed?" and
     honor `fan_out` (`never` → stay single-pass; `ask` → wait for a yes; `allowed` →
     proceed). Respect `budget`/`model`.
   - Split **read-only investigation only** into independent tracks (e.g. backend dead code,
     frontend dead code, god files, duplication/patterns, dependency modernization). Agents
     return structured evidence-backed findings; you synthesize. Edits stay in the main
     agent under Steps 6–7 — sub-agents never write. Use the report structure in
     `references/audit-report-template.md`.

9. **Self-check / quality gate (do not skip).** Before reporting, confirm every item:
   - [ ] Behavior anchor (or static proof) was green **before and after** every edit.
   - [ ] Every deletion cleared all four safe-deletion gates; unmet → advisory, not deleted.
   - [ ] Both sides of every changed contract were audited (producer **and** consumer).
   - [ ] No back-compat fallback papering over a contract you just changed — raise loudly or
         update all call sites.
   - [ ] Every finding carries a concrete `file:line` proof; no vibes-only claims.
   - [ ] The project's quality gate passed; the literal pass line is in the report.
   - [ ] No unrelated redesign was bundled in; the diff is small and reviewable.
   - [ ] A heavy report (repo sweep) was written to a file; only a tight summary is inline.
   - Any unchecked box → fix it or downgrade the affected change to an advisory finding
     before handing off.

## Output discipline

- **Editing pass:** summarize inline — what changed, why it is behavior-preserving, the
  literal verification pass line, and any residual risk.
- **Whole-repo audit:** write the full prioritized report to a file (e.g.
  `simplify-audit.md`) incrementally and emit only a tight inline summary (top kill-list
  items + top complexity offenders + line-count estimate). Do not dump the full report into
  the chat — it blows the output budget.
- Be blunt but precise. "If starting over" notes are welcome when the redo lens reveals a
  meaningfully simpler shape and migrating toward it is worth it.

## References

Only load the reference files you need.
- [references/checklist.md](references/checklist.md) — the `base:<id>` checks profiles can OVERRIDE/SUPPRESS.
- [references/ai-smell-signatures.md](references/ai-smell-signatures.md) — AI-slop signatures + the evidence each requires.
- [references/safe-deletion-bar.md](references/safe-deletion-bar.md) — the four-gate bar every deletion must clear.
- [references/audit-report-template.md](references/audit-report-template.md) — report structure for the opt-in whole-repo swarm.
