# Simplify checklist (stable `base:<id>` ids)

Each item has a stable id so a project profile can rebind or disable it without forking the
base. In `.agents/profiles/simplify.md`:

- `## OVERRIDE` → `base:<id> → <new binding>` (e.g. raise a threshold, change a definition).
- `## SUPPRESS` → `base:<id>` (turn the check off for this project, with a reason).
- `## ADD` → append project-specific checks (these have no base id; they are additive).

Only load this file when you need to apply a profile or cite a specific gate.

## Hard contract (never suppressible without explicit user say-so)

- **`base:behavior-preserved`** — No observable behavior changes: API responses, persisted
  formats, emitted events, UI states, background-job effects, CLI output. Bugs callers
  depend on count as behavior. A cleaner shape that changes behavior is a FAILURE.
- **`base:behavior-anchor`** — Establish a characterization / golden-master / snapshot or
  existing integration test that pins current behavior, **green before** editing and
  **green after**. No anchor → only static-provable changes; say so.
- **`base:safe-deletion-bar`** — Every deletion clears all four gates in
  `safe-deletion-bar.md`. Any gate unmet → advisory finding, not a deletion.
- **`base:both-sides-of-contract`** — For any contract-format change (key shape, event
  schema, persisted layout, function signature), audit BOTH the producer and every
  consumer before changing it.
- **`base:no-papered-fallback`** — Do not add a "for backward compat" fallback that papers
  over a contract you yourself just changed. Either raise loudly so the violation surfaces
  in tests, or update all call sites. Only relax for a proven real legacy path.

## Evidence & scope discipline

- **`base:evidence-required`** — Every finding carries a concrete proof: `file:line`, a grep
  showing zero callers, a line count, an import chain, a test, telemetry, or a project doc.
  No vibes-only claims.
- **`base:respect-intentional-arch`** — Do not flag a pattern the team chose deliberately
  (documented in CLAUDE.md/AGENTS.md/ARCHITECTURE.md/ADRs): hot/cold-state splits,
  bifurcated tooling, deliberate indirection, dual auth, etc.
- **`base:no-churn-edits`** — Skip changes that only rearrange code without reducing risk,
  complexity, or reader burden. Cosmetic-only churn is noise.
- **`base:no-tangled-commits`** — Do not bundle an unrelated redesign or a feature change
  into a cleanup pass. One concern per pass; small, reviewable diffs.
- **`base:incremental-strangler`** — Prefer small steps with the behavior anchor green
  between each (strangler-fig). Big-bang only for a small, fully-understood, low-coupling
  unit.

## Simplification targets (tune thresholds via OVERRIDE)

- **`base:dead-code`** — Remove provably-unused imports, exports, files, routes, feature
  flags, shims, and dependencies (only after `base:safe-deletion-bar`).
- **`base:duplicate-logic`** — Consolidate genuinely repeated transforms, validators,
  mappers, error handling, constants. Do not over-DRY incidental similarity.
- **`base:over-generalization`** — Collapse factories, registries, config surfaces, hooks,
  and helpers that serve exactly one real caller and add no policy.
- **`base:defensive-fog`** — Remove silent fallbacks, broad `except:`/catch-all handlers,
  and compatibility paths with no proven legacy caller; surface real errors instead.
- **`base:god-file`** — Flag files mixing multiple responsibilities, long functions, and
  high import counts. Default soft thresholds (OVERRIDE to retune): file > 300 lines is a
  size flag, > 500 lines warrants a split proposal; function > 60 lines; > 15 imports is a
  coupling flag. Thresholds are signals, not auto-fail.
- **`base:ai-prose-bloat`** — Trim comments that restate the code, theatrical names,
  "comprehensive" scaffolds for simple needs, and unnecessary layers.
- **`base:test-over-specification`** — Loosen tests that over-assert implementation detail
  (exact log strings, private call order) where behavior assertions suffice — without
  weakening genuine behavior coverage. New safety-net tests must fail-on-bug/pass-on-fix.

## Verification

- **`base:run-project-gate`** — Run the project's own quality gate (test / typecheck / lint
  / build) as the final word; report the literal pass line. Never pipe a gate command into
  `tail`/`head` (masks the exit code).
- **`base:shell-safety`** — Single-quote or heredoc commit messages (backticks run command
  substitution on zsh); check exit codes directly; never pipe-mask.
