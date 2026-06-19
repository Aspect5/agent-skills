# Docs-refresh drift checklist

Each item has a stable `base:<id>` so a project profile can `OVERRIDE base:<id>` or `SUPPRESS base:<id>` it. The base ships these ids; a profile never copies them. Apply every non-suppressed item against the in-scope docs. **Only load this file when you reach the drift-evidence step.**

A finding is admissible only with concrete proof: a `file:line`, a command + its output, or an existing ADR. "It reads wrong" is not a finding.

## Evidence & integrity

- `base:evidence-required` — Every factual claim you keep, add, or change must carry `file:line`, a verifiable command, or an ADR. Drop any claim you cannot back; do not soften it into a hedge.
- `base:no-invented-architecture` — Never state structure, flow, or behavior you have not verified from code/tests/CI/schemas. If unverifiable, list it as an open question, not a fact.
- `base:code-wins` — When a doc and the code disagree, the code is correct and the doc is the bug. When two docs disagree, re-derive from code. When an agent's claim conflicts with code, code wins.
- `base:preserve-warnings` — Do not delete a load-bearing warning, "do not change X", or intentional-complexity note unless you can prove from code/history it is obsolete. Stale-looking ≠ obsolete.

## Commands & workflow

- `base:commands-resolve` — Every command in the guidance docs must exist and run. Cross-check against `package.json` scripts, `pyproject.toml`, `Makefile`, `.github/workflows/`, and `scripts/`. Flag removed/renamed/relocated commands.
- `base:quality-gate-accurate` — The documented pre-commit / CI / lint / test gate must match what CI actually enforces. A doc that tells agents to run a gate that no longer exists (or omits one that does) is a blocker-class drift.
- `base:env-setup-accurate` — Setup/install/env-var instructions (`.env.example`, prerequisites, package manager, language version) must match the real toolchain.

## Structure & hot paths

- `base:hotpaths-exist` — Every file/dir in a "hot paths" / "key files" / pointer list must exist (`git ls-files`). Flag renamed, moved, or deleted entries; surface high-churn files that should be added.
- `base:sections-match` — Pointer-map section names in the short docs must match the actual headings/numbering in the canonical doc. A pointer to `§7` that no longer exists is a regression.
- `base:hierarchy-preserved` — Deep structural detail belongs in the canonical doc; short docs stay pointer-based. Flag deep detail that leaked into a pointer doc, and pointers that silently duplicate a long explanation.
- `base:routes-services-current` — Documented routes, services, layers, and module boundaries must match current code (routing tables, service modules, DI/wiring).

## Contracts & data

- `base:contract-both-sides` — For any documented contract (API schema, event shape, persisted JSON layout, queue/job payload, ref/citation format), verify BOTH the producer and the consumer. A doc that describes only one side invites a one-sided edit that breaks the other — flag the asymmetry explicitly.
- `base:schema-current` — Documented DB tables/columns/RLS/RPCs/migrations must exist in the schema/migration files. Flag references to dropped/renamed objects and undocumented new ones in scope.
- `base:deploy-current` — Documented deploy targets, env URLs, secrets, build steps, and cron/worker jobs must match the deploy config (Cloud Build / CI / IaC). Stale deploy docs cause wrong-environment mistakes.

## Hygiene

- `base:no-duplication` — One fact lives in one place. Flag the same explanation copied across docs; keep the canonical copy and replace the rest with a pointer.
- `base:no-time-sensitive` — Avoid "recently", "new", dated "as of" claims, and version-pinned prose that rots. Prefer durable, verifiable statements.
- `base:scope-respected` — Touch only in-scope docs. Do not revert or restate unrelated dirty-file edits; do not expand scope without asking.
