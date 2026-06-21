# Harness anatomy — the six components to inspect

**Agent = Model + Harness.** You can't tune the weights, so the harness is your whole lever. This file is the map: for each of the six components, what it *is*, where to find it in a repo, what **good** looks like, and the tells that it's broken. Score each component against the matching `base:<id>` block in `checklist.md`.

> Only load this when you're walking the anatomy in Workflow step 2. The script (`scripts/harness_inventory.py`) tells you what's *present*; this file tells you whether it's *good*.

---

## 1. Rule files — AGENTS.md / CLAUDE.md (and nested ones)

**What it is.** The natural-language instructions the agent loads as standing context: conventions, do/don't rules, workflow, quality gates, pointers. This is the agent's spec — and **specification is the new bottleneck**: a reliable agent is mostly a well-specified one.

**Where to find it.** Root `AGENTS.md` / `CLAUDE.md`; nested path-scoped ones (e.g. `frontend/AGENTS.md`); a profile under `.agents/profiles/`; `CONTRIBUTING`/`docs` style guides they point to.

**What good looks like.**
- Rules are concrete and testable — each names a trigger and an observable action ("before committing, run `make test`"), not a value ("write good code").
- No internal contradictions; nested rules refine, never reverse, root rules; precedence is stated.
- Lean and load-bearing — short enough to actually be read every turn; deep detail is pushed into dynamically-loaded references, not pinned here.
- Current — every command/path/symbol it names still resolves.

**Failure tells.** Aspirational philosophy with no operational instruction; a root rule and a subdir rule that conflict; a 600-line file that no one has pruned; a rule referencing a deleted script. *(checks: `base:rules-*`.)* Note: deep doc-accuracy auditing is `docs-refresh`'s job — here you judge whether the rules are *effective as a spec*, not whether every line is factually current.

---

## 2. Tools / MCP surface

**What it is.** The actions the agent can take beyond emitting text: built-in tools, MCP servers, and documented commands. The model can only do what the harness lets it reach — a capability with no tool gets improvised (badly) with shell.

**Where to find it.** `.mcp.json` / `mcp.json` / `.cursor/mcp.json`; the tool/permission allowlist in `.claude/settings*.json`; commands documented in the rule files; `package.json` scripts / `Makefile` targets that stand in for tools.

**What good looks like.**
- Sufficient — every capability the workflows assume is actually wired.
- Well-described — each tool's name + description lets the model pick it correctly and pass valid args; no two tools are confusable.
- Right-sized — not so many always-loaded tools that they crowd context or invite mis-selection.
- Dangerous tools are gated (approval, scope, or hook), and every declared MCP server actually resolves.

**Failure tells.** A workflow that references a tool that doesn't exist; a tool with an empty or generic description; two near-duplicate tools; a `delete`/`force-push`/prod-write tool exposed raw; a declared MCP server pointing at an uninstalled binary. *(checks: `base:tools-*`.)*

---

## 3. Guardrails / hooks

**What it is.** The **deterministic** checks the harness enforces regardless of what the model decides — hooks (pre-tool-use, pre-commit, pre-push), CI gates, secret scans, protected-branch blocks. Hooks are for **"what the agent should never forget"**: the invariants too important to leave to a prose request and the model's good intentions.

**Where to find it.** `.claude/settings*.json` `hooks`; `.husky/`; `.pre-commit-config.yaml`; `.github/workflows/` gates; lint/format/type config wired to run.

**What good looks like.**
- Every "must never get this wrong" operation has a deterministic check, not just a rule-file sentence.
- Checkable things (format, lint, types, secrets, protected branch) are enforced by code; prose is reserved for judgment.
- Each guardrail fires on the right trigger so it catches the mistake before it lands.
- Guardrails are proportionate — not so heavy they get habitually bypassed (`--no-verify`).

**The line that matters.** **Tests verify the deterministic parts; evals verify the non-deterministic parts.** Guardrails/hooks are the *deterministic* safety net — they should cover everything code can check. What code *can't* check (does the agent's prose answer meet the spec?) is an eval's job, which is `eval-author`'s domain — flag its absence, don't build it.

**Failure tells.** "Never commit secrets" with no secret-scan hook; a test gate that only runs post-merge; correctness left entirely to the model; a hook everyone disables. *(checks: `base:guardrails-*`.)*

---

## 4. Permissions / sandbox posture

**What it is.** The bounds on what the agent may do without asking — the allow/deny lists, sandbox mode, and approval gates that cap the blast radius of a bad action.

**Where to find it.** `.claude/settings*.json` `permissions` (allow/deny/ask); sandbox/approval mode config; CI runner scopes and credential grants; any `.codex`/`.cursor` permission equivalents.

**What good looks like.**
- Explicit and intentional — a stated posture, not wide-open-by-omission.
- Least-privilege — granted scope matches what the workflows actually need; no standing prod credentials or blanket fs/network access.
- Spend-gated — money/subagent-fan-out/paid-API operations require an approval or cost gate.
- Writes-gated — outward/irreversible actions (push, PR, prod mutation, deletion) pause for human approval.

**Failure tells.** No permission config at all on an agent that runs shell; a blanket allow-everything; standing prod creds in the default environment; subagent fan-out with no cost gate. *(checks: `base:sandbox-*`.)* A deliberately wide sandbox in throwaway CI is fine — expect it to be OVERRIDDEN in the profile, and don't flag it if it is.

---

## 5. Static-vs-dynamic context split

**What it is.** **Context engineering**: deciding what the agent always carries (static / always-on context) versus what it loads only when relevant (dynamic context — skills, references, on-demand file reads). The split is the single biggest lever on long-session reliability, because attention is finite and always-on context is paid for every turn.

**Where to find it.** The *size and content* of the always-on rule files; the presence and use of `.claude/skills` / `.agents/` references; whether large subsystem detail is pinned in AGENTS.md vs in a loaded-on-demand doc.

**What good looks like.**
- Static context holds durable, every-task facts only (core conventions, the quality gate, the precedence rules) — lean.
- Situational/large/occasional knowledge is dynamic: a skill or reference invoked when the task calls for it.
- Always-on footprint stays well under the budget so the working window isn't crowded (thresholds in `context-split-signals.md`).
- Precedence across overlapping sources is explicit.

**Failure tells (context rot).** A rule file that grows append-only forever; a rarely-touched subsystem's full API pinned always-on; skill-shaped knowledge jammed into AGENTS.md instead of being a dynamic skill; a 40-tool surface loaded every turn; stale rules and dead pointers never pruned. *(checks: `base:context-*`.)*

---

## 6. Observability

**What it is.** The ability to *see* what the agent did and whether it's drifting — logs, traces, tool-call records, transcripts, telemetry, eval scores, error-rate monitoring. You cannot fix a harness you can't observe, and you cannot tell a model failure from a harness failure without a signal.

**Where to find it.** Tracing/telemetry config (e.g. an observability MCP or SDK); CI test/eval history; a transcript or run-log convention; any regression-suite or eval scores tracked over time.

**What good looks like.**
- Some durable record of agent runs exists — not a black box.
- When a run fails, the signal is rich enough to attribute it to a harness cause (which rule/tool/missing guardrail), not just "it didn't work".
- A feedback loop would surface drift over time (eval scores, regression suite, error-rate monitoring, or at minimum a review habit).

**Failure tells.** No run record at all; failures that can only be described as "the model was dumb" with no way to point at config; no drift signal, so the harness degrades invisibly. *(checks: `base:observability-*`.)* Standing up the eval/regression suite is `eval-author`'s job — flag the *absence of a drift signal* and redirect; don't build the suite here.

---

## Scoring posture

For each component, return one of: **strong** (good-looks-like holds, no material defect), **adequate** (works but has should-fix gaps), **weak** (a defect that causes a named agent-failure), or **absent / N/A** (component genuinely not needed here — state why). The harness score is the honest roll-up of the six, weighted toward the components whose defects cause the failures the user actually reported.
