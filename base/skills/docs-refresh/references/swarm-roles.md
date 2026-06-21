# Doc-refresh swarm roles (opt-in, read-only)

Load this **only** when launching the multi-agent swarm — i.e. the user explicitly asked for subagents/parallel agents, or the scope is a whole-repo drift audit too large for one pass. Otherwise audit single-pass yourself; that is the default and the leanest path.

## Before dispatching (budget gate)

1. **Cost preflight.** State the count: "This dispatches ~5 read-only subagents — proceed?" Scale the count down for smaller scopes (a frontend-only refresh may need only the frontend + hygiene agents).
2. **Honor the profile.** `fan_out: allowed` → proceed; `fan_out: ask` → wait for an explicit yes; `fan_out: never` → do not swarm, fold the roles into your own single pass. Cap subagent count against `budget`. On a cheaper model prefer fewer agents + deterministic greps; on a more capable model more parallel prose is fine.
3. **Read-only contract.** Every agent is read-only. Ask for evidence + proposed doc edits, never direct file changes. You synthesize and apply edits after approval. Run agents in parallel when independent.

Each agent returns: findings as `claim → file:line evidence → verdict (accurate | stale | missing | misleading)`, proposed edits with target file/section, and anything intentionally complex the docs should preserve.

## Agent 1 — Backend / core architecture drift

Read backend routing, auth, request pipeline, core services, business-logic modules, background workers, caching/state, repositories, schemas, and migrations. Compare to the canonical architecture doc.

Return: stale/missing/misleading architecture sections; exact file evidence; suggested edits; intentional complexity to preserve.

## Agent 2 — Frontend / client architecture drift

Read frontend routing, state stores, data-fetching/streaming clients, realtime hooks, key components, and any design-system doc. Compare to the canonical doc and the hot-path lists in the short docs.

Return: stale/missing frontend sections; files that should be added to or removed from hot paths; current commands and validation surfaces; evidence per recommendation. (Skip if the repo has no frontend.)

## Agent 3 — Developer-workflow drift

Inspect `scripts/`, CI/CD, build/deploy config, test commands, quality gates, dev startup, env examples, GitHub workflows, deploy docs, and package metadata. Compare to the documented commands and gates.

Return: outdated/missing commands; misleading quality-gate guidance; deploy/env changes the docs miss; evidence from the scripts/config files. Covers `base:commands-resolve`, `base:quality-gate-accurate`, `base:env-setup-accurate`, `base:deploy-current`.

## Agent 4 — Contract & data-shape audit

Inspect API schemas, event contracts, persisted JSON layouts, ref/citation flows, DB/RLS references, job payloads, and producer/consumer pairs. Covers `base:contract-both-sides`, `base:schema-current`.

Return: contract formats that changed but the docs did not; producer AND consumer evidence for each; schema/table/RPC references to document or remove; explicit warnings where a doc risks encouraging a one-sided contract edit.

## Agent 5 — Doc hygiene & redundancy

Read the in-scope docs for duplication, stale claims, deep detail leaking into short pointer docs, missing/broken pointers, time-sensitive wording, and outdated warnings. Covers `base:no-duplication`, `base:hierarchy-preserved`, `base:sections-match`, `base:no-time-sensitive`.

Return: what should move from a pointer doc into the canonical doc; what to shorten or delete; pointer-map inconsistencies; wording that could mislead future agents. Do NOT propose deleting a warning unless it cites code/history proving it obsolete.

## After the swarm

Merge findings into one edit plan written to a file. Resolve any agent-to-agent conflict by re-checking source code directly — code is the tiebreaker, not the more confident agent. Then return to the main workflow (approval pause → apply → validate every reference → self-check).
