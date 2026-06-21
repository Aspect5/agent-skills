# Harness audit checklist (stable `base:<id>` ids)

The per-component check catalog. Every check has a stable id so a project profile can rebind or disable it:

- `## OVERRIDE` → `base:<id> → <new rule>` rebinds a check (e.g. a repo that *intends* a wide sandbox in throwaway CI rebinds `base:sandbox-posture-explicit`).
- `## SUPPRESS` → `base:<id>` turns a check off for that project.
- `## ADD` → appends project-specific checks (give them project ids, not `base:`).

The base ships these ids; a profile never copies them, it references them. Score only the components in scope; each check produces a finding ONLY with a concrete anchor (`file:line`, a named missing file/tool, or a measured signal), and every finding then runs the FP-suppression gauntlet in `advisory-report-template.md`. Every finding also names **the agent-failure it causes** — that link is what makes "most agent failures are configuration failures" actionable rather than a slogan.

> Only load this file when you're actually scoring. The ids are the contract surface — don't renumber them.

## rules — AGENTS.md / CLAUDE.md quality (`base:rules-*`)

- `base:rules-unambiguous` — Rules are concrete and testable, not vibes. Flag unfalsifiable directives ("write clean code", "be careful", "follow best practices") that an agent cannot operationalize or be checked against. *Causes:* ignored-rule / inconsistent behavior. A good rule names a trigger and an observable action.
- `base:rules-no-contradiction` — No two rules conflict, and no nested/path-scoped rule contradicts a root rule (e.g. root says "never edit `main`", a subdir doc says "commit fixes directly"). *Causes:* nondeterministic, context-dependent behavior — the agent silently picks one.
- `base:rules-discoverable` — Critical rules live where the agent will actually load them (root `AGENTS.md`/`CLAUDE.md` or a reliably-loaded pointer), not buried in a deep README the agent never reads. A load-bearing rule no agent sees is equivalent to an absent rule. *Causes:* ignored-rule.
- `base:rules-actionable-not-aspirational` — Rules describe what to do, not just what to value. Flag walls of philosophy with no operational instruction. *Causes:* drift under pressure.
- `base:rules-current` — Rules don't reference removed commands, renamed paths, or dead workflows. (Deep accuracy auditing of doc prose is `docs-refresh`'s job — here, only flag a rule so stale it actively *misdirects* the agent, and redirect the full sweep to docs-refresh.) *Causes:* wrong-action from a confidently-wrong instruction.

## tools / MCP surface (`base:tools-*`)

- `base:tools-sufficient` — Every capability the rule files / workflows assume the agent has is actually wired (a tool or MCP server, or a documented command). Flag a workflow that says "deploy with the deploy tool" when no such tool exists — the agent will improvise with raw shell. If the profile sets `expected_tools`, every tool it names must be wired **and** described — a missing or undescribed one is a finding. *Causes:* invented/unsafe workarounds.
- `base:tools-described` — Each exposed tool/MCP server has a name + description good enough for the model to *select it correctly and pass valid args*. Flag tools with empty, generic, or misleading descriptions, or overlapping tools the model can't disambiguate. A tool the model can't tell when to use is dead weight. *Causes:* wrong-tool selection.
- `base:tools-no-dangerous-ungated` — No destructive or high-blast-radius tool (delete, force-push, prod write, arbitrary code exec, spend) is exposed without a guard (approval gate, permission scope, or hook). *Causes:* silent-bad-write / irreversible action.
- `base:tools-not-overloaded` — The tool surface isn't so large it crowds the context or invites mis-selection. Flag dozens of near-duplicate or never-used tools always loaded. (Cross-references `base:context-tools-bloat`.) *Causes:* wrong-tool + context rot.
- `base:tools-mcp-reachable` — Declared MCP servers actually resolve (command/URL present, not a dangling reference to an uninstalled binary or dead endpoint). A declared-but-broken server is worse than none — the agent assumes a capability it doesn't have. *Causes:* silent capability gap.

## guardrails / hooks (`base:guardrails-*`)

- `base:guardrails-present-for-danger` — For every operation the agent must never get wrong, there is a **deterministic** check the harness enforces — a hook, a pre-commit, a CI gate — not a polite request in a rule file. "Never commit secrets" with no secret-scan hook is a wish, not a guardrail. *Causes:* the exact failure the rule was trying to prevent.
- `base:guardrails-deterministic-not-prose` — Things that can be checked by code (format, lint, types, secret scan, protected-branch block) are enforced by code, not delegated to the model's good intentions. Prose is for judgment; hooks are for "what the agent should never forget". Flag a critical invariant left to prose alone. *Causes:* intermittent regressions.
- `base:guardrails-right-trigger` — Each guardrail fires on the right event (pre-commit / pre-push / pre-tool-use / CI) so it actually catches the mistake before it lands. A test gate that only runs in CI after a force-push to prod fired too late. *Causes:* late detection / shipped defect.
- `base:guardrails-not-overzealous` — Guardrails don't block so much that the agent (or human) routinely bypasses them (`--no-verify` as a habit). An always-skipped hook is an absent hook. *Causes:* normalized bypass → silent failure.

## permissions / sandbox posture (`base:sandbox-*`)

- `base:sandbox-posture-explicit` — The permission/sandbox posture is stated and intentional (an allow/deny list, a sandbox mode), not implicitly wide-open by omission. Flag an absent or default-permissive posture where the agent can run arbitrary commands unprompted. *Causes:* unbounded blast radius. (A repo that *intends* a wide sandbox should OVERRIDE this.)
- `base:sandbox-least-privilege` — Granted permissions match what the workflows actually need — no standing prod credentials, no blanket filesystem/network access where a narrow scope would do. *Causes:* over-broad blast radius on a single bad action.
- `base:sandbox-spend-gated` — Operations that spend money, fan out subagents, or call paid APIs at scale require an approval/cost gate, not silent execution. *Causes:* runaway cost.
- `base:sandbox-writes-gated` — Outward/irreversible writes (push, PR, prod mutation, file deletion outside a scratch area) require a human-approval pause. *Causes:* silent irreversible change.

## static-vs-dynamic context split (`base:context-*`)

- `base:context-split-sound` — Durable, always-true, every-task facts live in static (always-on) context; situational/large/occasional knowledge is loaded dynamically (skills, references, on-demand reads). Flag situational detail (a rarely-touched subsystem's full API) pinned into always-on context. *Causes:* context rot, diluted attention.
- `base:context-no-rot` — Always-on context is lean and current — no stale rules, no dead pointers, no duplicated explanations, no ever-growing "append-only" rule file. Measure it: flag an always-on footprint large enough to crowd the working window (see `context-split-signals.md` for thresholds). *Causes:* degraded long-session behavior, ignored later rules.
- `base:context-skills-dynamic` — Knowledge that should be a dynamically-loaded skill/reference (invoked when relevant) isn't instead jammed permanently into AGENTS.md. Skills are the dynamic-context mechanism; pinning their content always-on defeats the point. *Causes:* over-stuffed always-on context.
- `base:context-tools-bloat` — The always-loaded tool/MCP descriptions don't themselves dominate the context budget. A 40-tool always-on surface is context the model pays for every turn. (Cross-references `base:tools-not-overloaded`.) *Causes:* context rot + mis-selection.
- `base:context-precedence-clear` — When multiple context sources overlap (root vs nested rule files, profile vs base, doc vs code), the precedence is stated and unambiguous, so the agent isn't resolving conflicts by guess. *Causes:* nondeterministic behavior.

## observability (`base:observability-*`)

- `base:observability-present` — There is *some* way to see what the agent did — run logs, traces, tool-call records, a transcript, or telemetry — not a black box. You cannot fix a harness you can't observe. *Causes:* undiagnosable, recurring failures.
- `base:observability-failure-attributable` — When the agent fails, the signal is rich enough to attribute the failure to a harness cause (which rule, which tool, which missing guardrail) rather than just "it didn't work". *Causes:* failures misattributed to "the model" → no fix.
- `base:observability-drift-detectable` — There's a feedback loop that would surface drift over time (eval scores, a regression suite, error-rate monitoring, or at minimum a review habit). A harness with no drift signal degrades invisibly. *Causes:* slow, unnoticed regression. (Standing up the eval itself is `eval-author`'s job — here, only flag the *absence* of a drift signal and redirect.)

## meta (`base:failure-*`) — cross-cutting

- `base:failure-traced-to-config` — Every finding in the report ties the observed/likely agent failure to a specific harness defect (a rule, a tool, a guardrail, the context split, the permissions, or the observability gap). A finding that can't name the failure it causes is a style opinion, not a harness defect — drop or downgrade it. This is the operational form of "most agent failures are configuration failures": if you can't point at the config, you haven't found the cause.
