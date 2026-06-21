# Context-split signals — static vs dynamic, and the rot signatures

**Context engineering** is the discipline of deciding what the agent always carries versus what it loads on demand. This file is the rubric for scoring the static-vs-dynamic split (`base:context-*`): what belongs where, the rot signatures to look for, and rough thresholds so "too big" is a measured claim, not a vibe.

> Only load this when scoring the context split. The inventory script gives you the always-on token estimate; this file tells you how to read it.

## The split, stated plainly

| | **Static context** (always-on) | **Dynamic context** (loaded when relevant) |
|---|---|---|
| Holds | Durable, every-task facts: core conventions, the quality gate, branch/PR rules, precedence rules, the pointer map | Situational/large/occasional knowledge: a subsystem's full API, a rare workflow, a big reference table, a skill's procedure |
| Mechanism | Root `AGENTS.md` / `CLAUDE.md`, the always-loaded tool descriptions | Skills, `references/*.md` loaded on demand, on-demand file reads, MCP resources fetched when needed |
| Cost | Paid **every turn** — competes with the working window | Paid **only when invoked** |
| Test | "Is this true and needed on *every* task?" → static | "Is this needed only *sometimes*, or large?" → dynamic |

The governing idea: attention is finite and always-on context is the most expensive context you have. Static context should be **small, durable, and load-bearing**; everything else should be a dynamic load. Skills exist precisely to be the dynamic-context mechanism — pinning a skill's content permanently into AGENTS.md defeats the purpose.

## What belongs in static (always-on)

- The non-negotiable rules that apply to *every* task (protected-branch policy, "run the gate before commit", security must-nots).
- The quality-gate command(s) and how to run them.
- The precedence map (which doc/profile/source wins on conflict).
- A short **pointer map**: "deep architecture → `ARCHITECTURE.md §N`; deploy → `docs/deploy.md`; this subsystem → its skill." Pointers, not the content.

## What belongs in dynamic (loaded when relevant)

- A subsystem's full API or schema you touch occasionally.
- A rare or specialized workflow (a release dance, a migration recipe).
- Large reference tables, catalogs, rubrics (like this file).
- Anything skill-shaped: a procedure with a trigger — it should be a skill the agent loads when the trigger fires, not always-on prose.

## Rot signatures (flag these)

1. **Append-only growth.** The rule file only ever grows — every incident adds a paragraph, nothing is ever pruned. Tell: a long file with overlapping/duplicated rules and a git history of pure additions.
2. **Situational detail pinned always-on.** A rarely-touched area's full detail lives in AGENTS.md, paid for on every unrelated task. Should be a dynamic reference/skill.
3. **Skill-shaped knowledge inlined.** A trigger-and-procedure block ("when doing X, do A/B/C") sitting in always-on context instead of being a dynamic skill. *(check: `base:context-skills-dynamic`.)*
4. **Tool-surface bloat.** Dozens of always-loaded tool/MCP descriptions dominating the budget — context the model pays for every turn and that invites mis-selection. *(checks: `base:context-tools-bloat`, `base:tools-not-overloaded`.)*
5. **Stale always-on rules.** Rules naming removed commands, renamed paths, dead workflows — still loaded every turn, still misdirecting. (Full doc-accuracy sweep → `docs-refresh`; here, flag that stale always-on content is *actively misdirecting* and pulling its weight in tokens.)
6. **Duplicated facts.** The same explanation copied across root and nested files (or across AGENTS.md and CLAUDE.md) — drift waiting to happen, and double the always-on cost.
7. **Unclear precedence.** Overlapping root/nested/profile sources with no stated winner, so the agent resolves conflicts by guess. *(check: `base:context-precedence-clear`.)*

## Rough thresholds (calibrate, don't worship)

These are heuristics for turning "feels big" into a measured signal. The inventory script reports a rough always-on token estimate (chars/4); use it as the anchor and adjust to the project.

- **Always-on rule footprint:**
  - **≲ 2k tokens** — lean; healthy.
  - **2k–5k tokens** — getting heavy; check that everything in it is genuinely every-task. Should-fix if situational detail is present.
  - **≳ 5k tokens** — likely bloated; almost certainly contains dynamic-worthy content. Flag context rot and recommend extracting to skills/references. (Profiles can set `context_budget_tokens` to override this band.)
- **Always-on tool/MCP descriptions:** if the tool surface descriptions alone approach the rule-file size, that's `base:context-tools-bloat`.
- **Single-rule-file length:** a root rule file past ~300–400 lines is a strong prompt to look for extractable dynamic content — length alone isn't a defect, but it's where rot hides.

A big always-on context isn't automatically wrong (a genuinely complex, every-task-relevant invariant set can justify it) — but it must *earn* its always-on cost. If any line wouldn't be missed on a typical task, it belongs in dynamic context. Tie every threshold finding to the agent-failure it causes (degraded long-session behavior, later-rule neglect, mis-selection) per `base:failure-traced-to-config`.
