# Tailoring base skills to a project (for tailoring agents)

This guide is for an **agent** specializing these base skills to a specific project. Read it, then author a profile in the **project's own repo**. You never edit the base skills.

## Mental model

A base skill is **pure process**. Everything project-specific is **data it reads at runtime**:
1. `AGENTS.md` / `CLAUDE.md` (root → cwd) — already in the model's context.
2. `.agents/profiles/<skill>.md` — the per-project profile (you author this).
3. Discovered config — `package.json` scripts, `pyproject.toml`/`ruff.toml`, `Makefile`, `.github/workflows/*`.
4. Skill defaults — when nothing above is present.

The skill runs unmodified with no profile, and better with one. Your job is to supply the data, not change the process.

## Your job, step by step

1. **Learn the project.** Read its `AGENTS.md`/`CLAUDE.md`, `CONTRIBUTING`, lint/test/CI config, directory shape, migration tool, security surface. Note what CI already enforces (the skill must not re-flag it).
2. **Pick the skill's override hooks.** Each base skill exposes stable `base:<id>` ids — the authoritative list is in that skill's `references/checklist.md` (and `references/reviewer-dimensions.md` for `code-review`). Grep it:
   ```bash
   grep -oE 'base:[a-z0-9-]+' ~/.codex/skills/<skill>/references/*.md | sort -u
   ```
3. **Author `<project>/.agents/profiles/<skill>.md`** — copy `profiles-template/code-review.md` (the canonical example) and adapt it. Set the frontmatter knobs, then add `ADD` / `OVERRIDE base:<id>` / `SUPPRESS base:<id>` blocks.
4. **Set the budget/model knobs** (below) so the skill self-throttles.
5. **Keep it confidential.** Proprietary/stack detail lives only here, in the project repo — never in `agent-skills`.

## The profile (shape the base depends on)

```markdown
---
skill: code-review
extends: code-review@1
project: <name>
commands: { lint: "...", test: "...", ci: "..." }   # omit → skill auto-detects
severity_floor: should-fix          # blocker | should-fix | nit
focus_paths: [ ... ]                 # weight findings here higher
ignore_paths: [ ... ]                # never flag (e.g. generated code)
model: gpt-5.5                       # or gpt-5.4
budget: { period: day, limit_usd: 100 }
fan_out: ask                         # allowed | ask | never
---
## ADD
- <new project-specific rule appended to the checklist>
## OVERRIDE
- base:migration-reversible → <rebind a default, e.g. migrations use an in-house tool; require its down-stanza, not a SQL rollback>
## SUPPRESS
- base:security-secrets   # <reason this project opts out, e.g. a dedicated gitleaks gate already covers this>
```

## Budget / model knobs

| Knob | Effect |
|---|---|
| `model: gpt-5.4` | Skill prefers deterministic scripts + lower-freedom steps (weaker model). `gpt-5.5` → more prose latitude. |
| `budget` | The skill states rough cost before expensive work and stays within the period limit. |
| `fan_out: never` | No multi-agent fan-out — single-pass only (cheapest). `ask` → cost preflight + confirm. `allowed` → fan out freely. |

Tight-budget project (e.g. monthly cap, weaker model) → `model: gpt-5.4`, `fan_out: never` (or `ask`), modest `budget`. Roomy project → `gpt-5.5`, `fan_out: allowed`.

## Override hooks by skill (where to find them)

Each skill's guardrails/checks are addressable by `base:<id>`. The lists live in the skill's `references/`:

| Skill | Hook surface (see `references/`) |
|---|---|
| `code-review` | ~70 ids by dimension: `correctness-*`, `security-*`, `perf-*`, `api/contract-*`, `migration-*`, `tests-*`, `design-*`, `docs-*`, `platform-*`, `silent-*` (`checklist.md`, `reviewer-dimensions.md`) |
| `simplify` | `safe-deletion-bar`, `behavior-anchor`, `dead-code`, `over-generalization`, `duplicate-logic`, `god-file`, … (`checklist.md`, `ai-smell-signatures.md`) |
| `churn-audit` | `missing-boundary`, `leaky-abstraction`, `org-ownership`, `contract-coordination`, … (`signals.md`, `diagnosis-checklist.md`) |
| `bug-swarm` | `repro-required`, `adversarial-siblings`, `abstain-over-guess`, `minimal-blast-radius`, `scope-local-no-schema`, … (`checklist.md`, `overfit-guards.md`) |
| `design-tradeoff` | `three-distinct-options`, `reversibility-class`, `weighted-table`, `back-out-path`, `fitness-function`, … (`checklist.md`, `scoring-axes.md`) |
| `docs-refresh` | `no-invented-architecture`, `contract-both-sides`, `hierarchy-preserved`, `quality-gate-accurate`, … (`checklist.md`) |
| `handoff` | `has-current-state`, `every-claim-has-proof`, `next-command-runnable`, `pinned-shas`, … (`checklist.md`) |

## Worked example (stack-agnostic)

A project whose CI already runs formatting + types, uses a custom migration tool, and is on a tight monthly budget tailors `code-review`:

```markdown
---
skill: code-review
extends: code-review@1
project: acme
commands: { test: "make test", ci: "make ci" }
severity_floor: should-fix
focus_paths: [ "services/billing/", "services/auth/" ]
model: gpt-5.4
budget: { period: month, limit_usd: 200 }
fan_out: ask
---
## ADD
- Every new outbound HTTP call must have a timeout and a typed error path.
## OVERRIDE
- base:migration-reversible → migrations use the in-house `dbx` tool; require a `dbx down` stanza, not a SQL rollback.
## SUPPRESS
- base:security-secrets   # a dedicated gitleaks pre-commit gate already covers this; don't double-report
```

Running `code-review` in `acme`: it discovers `make test`/`make ci`, won't re-flag format/types (CI owns them), weights billing/auth, adds the HTTP-timeout rule, reinterprets the reversible-migration check for `dbx`, drops secret-scanning (deduped against the existing gate), and — because `model: gpt-5.4` + `fan_out: ask` + a monthly cap — runs the lean single-pass path and asks before spawning per-dimension reviewers. **The base skill is byte-identical to every other project's.**

## Rules

- Never edit `base/`. To change behavior for one project, edit *its* profile. To improve *all* projects, propose a base change (it must stay project-agnostic).
- A profile is additive/rebinding only — `ADD` / `OVERRIDE base:<id>` / `SUPPRESS base:<id>`. If you find yourself wanting to rewrite the process, that's a base change, not a profile.
- Confidential detail → project repo only.
