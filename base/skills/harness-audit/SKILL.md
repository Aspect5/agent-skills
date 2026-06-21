---
name: harness-audit
description: >-
  Produces an evidence-backed audit of a repo's agent HARNESS — the scaffolding
  around the model: rule files (AGENTS.md / CLAUDE.md), the tools/MCP surface,
  guardrails/hooks, permissions/sandbox posture, the static-vs-dynamic context
  split, and observability — scored against "Agent = Model + Harness", with
  prioritized fixes for the missing tools, vague or contradictory rules, absent
  deterministic guardrails, and context rot that cause agent failures. Advisory
  by default — it diagnoses and recommends; it does not rewrite the harness.
  Use when asked to audit or improve an agent / Claude Code / Codex setup, assess
  AGENTS.md/CLAUDE.md quality, diagnose why an agent keeps failing, drifting, or
  ignoring its rules, review the harness or agent configuration, or "is our agent
  setup any good". Do not trigger for: reviewing application code in a diff (use
  code-review); fixing factual drift in prose/architecture docs so they match the
  code (use docs-refresh — that fixes doc ACCURACY; this judges harness
  EFFECTIVENESS); BUILDING a specific guardrail/hook/check (use guardrail-author —
  this only diagnoses that one is missing); standing up an eval/verification suite
  (use eval-author); implementing the agent or its tools; or general Q&A.
---

# Harness Audit

## Overview

An agent is **Model + Harness** — and since you don't control the model weights, almost everything that makes an agent reliable lives in the harness: the rule files it reads, the tools it can call, the guardrails that catch what it must never forget, the permissions that bound it, the context it's fed, and the observability that lets you see it drift. **Most agent failures are configuration failures**, not model failures. This skill audits that harness against a fixed anatomy and returns a prioritized, evidence-backed advisory — every finding anchored to a real `file:line`, a missing file, or a measured signal.

The hard contract: **advisory only**. It diagnoses harness defects and recommends fixes ranked by the agent-failure they cause; it does not rewrite AGENTS.md, author a hook, or change a permission. When the user wants a fix built, hand off (guardrail-author for a hook/check, docs-refresh for doc accuracy, eval-author for a verification suite) — never mutate the harness inside the audit.

> Output discipline: write the full advisory to a file (default `harness-audit.md`)
> incrementally as each component is scored, and emit only a tight summary inline
> (the harness score, the top 3 defects, the single best first move, the report
> path). Never paste the whole report or long rule-file excerpts into the chat.

## Step 0 — Context-Absorption Prelude

Run this before any analysis. Never fail for lack of a profile — fall back to defaults.

1. **Notice what's already in context.** `AGENTS.md` / `CLAUDE.md` (root and nested, path-scoped) are typically already loaded — and here they are *the subject under audit*, not just guidance. Read them as artifacts to be scored: note their size, their rules, and their pointers. Do not re-fetch what you already hold.
2. **Read the profile if present:** `.agents/profiles/harness-audit.md`. If it exists, apply its frontmatter knobs (`model`, `budget`, `fan_out`, `focus_paths`, `ignore_paths`, plus optional `context_budget_tokens` (context-band override) and `expected_tools` (checked by `base:tools-sufficient`)) and its `## ADD` / `## OVERRIDE base:<id>` / `## SUPPRESS base:<id>` directives against the checklist in `references/checklist.md`. A SUPPRESSed `base:<id>` is never scored; an OVERRIDDEN one uses the project's rebinding (e.g. a repo that deliberately runs sandbox-off in CI can OVERRIDE `base:sandbox-posture-explicit`).
3. **Resolve commands and harness locations** in this precedence, first hit wins: profile values → introspect the repo (`package.json` / `pyproject.toml` / `Makefile` / `.github/workflows/`; `.claude/`, `.cursor/`, `.codex/`, `.mcp.json`/`mcp.json`, `.agents/` for harness config) → ask the user once if a critical location is genuinely ambiguous → ecosystem default. Use the inventory helper to do the discovery deterministically: `python3 "<path-to-skill>/scripts/harness_inventory.py" --json`. Never invent a harness location.
4. **Fall back to defaults** when no profile and no override exist — the skill must run unmodified with zero config. Absence of a profile is normal, not an error.

Honor the budget posture from the start: `fan_out: never` ⇒ stay single-pass; `fan_out: ask` ⇒ run the cost preflight before any fan-out; a cheaper `model` ⇒ lean on the inventory script's numbers and prefer lower-freedom, scripted checks over open-ended prose; a more capable `model` ⇒ more architectural-judgment latitude.

## Workflow

### 1. Inventory the harness (deterministic, do not eyeball)

Run the bundled script first — it self-roots via `git rev-parse --show-toplevel`, so it works from any subdirectory:

```bash
python3 "<path-to-skill>/scripts/harness_inventory.py" --json
```

It reports presence + size of rule files (`AGENTS.md`, `CLAUDE.md`, nested ones), skills/commands dirs (`.claude/skills`, `.claude/commands`, `.agents/`), hook config (`.claude/settings*.json` hooks, pre-commit, `.husky/`), MCP config (`.mcp.json` / `mcp.json` / `.cursor/mcp.json`), permission/sandbox settings, and CI workflows — plus a rough token estimate of the always-on context. Treat its output as the **map**, not the verdict: a present file can still be vague, and an absent one is only a defect if that component is actually needed here. If the script can't run (no git, no python), fall back to a manual `git ls-files` sweep of the same locations and say so.

### 2. Read the harness anatomy and bind each component to evidence

Walk the six components in `references/harness-anatomy.md`, and for each one gather the concrete evidence the checklist needs — never score from memory:

- **Rule files** — AGENTS.md/CLAUDE.md: are the rules unambiguous and testable, or vague ("write clean code")? Do any two rules (or a rule and a nested rule) contradict? Is it bloated past the point of being read?
- **Tools / MCP surface** — is every tool the workflows assume actually wired and *described* well enough to be picked correctly? Is a needed capability missing (forcing the agent to improvise with shell)? Is a dangerous tool exposed with no guard?
- **Guardrails / hooks** — are the deterministic checks that catch "what the agent must never forget" present (format/lint/test/secret-scan on the right trigger), or is correctness left entirely to the model's good intentions?
- **Permissions / sandbox** — is the posture explicit and least-privilege, or implicitly wide-open? Are destructive/spend operations gated?
- **Static-vs-dynamic context split** — is always-on context lean and durable, with situational knowledge loaded dynamically (skills, references) — or is everything stuffed into one ever-growing always-on file (context rot)?
- **Observability** — can an operator tell *whether the agent is drifting*: are runs traced/logged, are failures attributable to a harness cause, is there a feedback loop?

Resolve context before judging: a rule that looks vague may be operationalized by a hook; a "missing" tool may be intentionally shell-only. Missing-context judgments are the #1 false-positive source — see the gauntlet in `references/advisory-report-template.md`.

### 3. Score each component against the checklist

Apply the stable `base:<id>` checks in `references/checklist.md` (respect profile OVERRIDE/SUPPRESS). Each finding must carry: a concrete anchor (`file:line`, a named missing file/tool, or a measured signal like "always-on context ≈ 14k tokens"), the **agent-failure it causes** (drift / ignored-rule / wrong-tool / silent-bad-write / unobservable-failure), a severity, and a confidence. **No anchor ⇒ not a finding.** This is the heart of "most agent failures are configuration failures": every defect names the failure it produces.

### 4. Map symptoms to harness causes (when the user reports a failing agent)

If the trigger is "the agent keeps doing X" rather than a cold audit, start from the symptom and work back to the missing harness piece using `references/failure-mode-catalog.md` (e.g. *ignores a rule* → rule is buried/contradicted/non-deterministic where a hook is needed; *invents a workflow* → missing or mis-described tool; *ships a bad write* → absent guardrail; *degrades over a long session* → context rot / over-stuffed always-on context). Confirm the mapped cause against real evidence before asserting it — the catalog is a hypothesis generator, not a verdict.

### 5. Score the harness and write the advisory (output discipline)

Compute the component-by-component harness score and write the full advisory to a file (default `harness-audit.md`, or a profile/user path) **incrementally**, using `references/advisory-report-template.md`: Executive Read (one-line posture + score) → component scorecard → per-defect entries (evidence → the agent-failure it causes → recommended fix → which skill owns the fix) → an ordered Action Plan (highest agent-failure-reduction first, each with payoff/risk/first safe step) → what to **leave alone** (intentional, load-bearing harness choices). **Emit only a 5–8 line summary inline** (score, top 3 defects, best first move, report path).

### 6. Budget & fan-out posture (cost preflight before any multi-agent run)

Single-pass, single-agent is the **default** — the inventory script does the deterministic heavy lifting, so one careful pass covers most audits at the lowest cost. **Before any multi-agent fan-out:**

- Honor the profile `fan_out` knob: `never` → never fan out (single pass only); `ask` → state the cost preflight ("this is ~N read-only subagents, one per harness component lens — proceed?") and wait for a yes; `allowed` → proceed but still announce the count.
- Honor `budget` and `model`: on a cheaper model or a tight budget, prefer the lean single-pass scripted path; on a more capable model with headroom, parallel component-lens subagents and more prose latitude are fine.
- Fan out only when the harness is genuinely large (many nested rule files, a big MCP surface, multiple skills) and the profile permits it. Suggested independent read-only lenses: Rules & Context lens, Tools/MCP lens, Guardrails & Permissions lens, Observability lens. **Each subagent returns evidence only and edits nothing.**

### 7. Human-approval pause before any write

This skill **reports**; it does not mutate the harness by default. Do not edit a rule file, add a hook, change a permission, or scaffold an MCP entry unless the user explicitly asks. If they do, **pause for explicit approval on the specific change**, then hand off to the owning skill (guardrail-author for a hook/check, docs-refresh for doc-accuracy edits, eval-author for an eval) rather than performing the harness mutation inside this audit. Use shell-safe command construction (single-quote / heredoc any body — never backtick-substitute on zsh).

### 8. Self-check / quality gate (run before reporting)

Confirm every box — report the literal results, never assert:

- [ ] The inventory came from `harness_inventory.py` (or a stated manual fallback); component presence/size is measured, not guessed.
- [ ] Every one of the six anatomy components was scored, including the ones that came back clean — silence is not "checked"; an `N/A` is stated with its reason.
- [ ] Every finding carries an anchor (`file:line`, named missing file/tool, or measured signal), the **agent-failure it causes**, a severity, and a confidence; every `base:<id>` used is honored (no SUPPRESSed id was scored; OVERRIDDEN ids used the rebinding).
- [ ] Each finding survived the FP-suppression gauntlet (a "missing" piece isn't actually present-elsewhere; a "vague" rule isn't operationalized by a hook; an intentional/OVERRIDDEN posture isn't flagged).
- [ ] Each recommendation names the owning skill for the fix (guardrail-author / docs-refresh / eval-author) where one applies, and the audit itself made **no** harness mutation.
- [ ] The full advisory is in the file; only a tight summary went inline.
- [ ] No write/spend happened without explicit approval + a cost preflight for any fan-out.

If any box fails, fix it before reporting. A clean harness is a valid result — say so and list the evidence checked.

## Guardrails

- **Advisory only.** Never rewrite AGENTS.md/CLAUDE.md, author a hook, change a permission/sandbox setting, or add an MCP entry inside this audit. Diagnose, recommend, and hand off.
- **Evidence or it doesn't ship.** Every finding needs a `file:line`, a named missing file/tool, or a measured signal. "The setup feels weak" is not a finding.
- **Respect intentional posture.** A deliberately wide permission in a throwaway sandbox, a terse-by-design rule file, or a shell-only-by-choice workflow is not automatically a defect — check the profile's OVERRIDEs and the repo's own stated intent before flagging.
- **Don't leak secrets.** MCP/hook/permission config can contain tokens or signed URLs — reference them by name and mark "redacted"; never paste a credential into the report.
- **Stay in the harness.** Application-code bugs, doc factual-drift, and building the actual guardrail/eval are other skills' jobs — note and redirect, don't absorb them.
- **Read-only by default.** All discovery is read-only; the only writes are the advisory file and (with approval) a handoff.

## References

Load only the reference files you need:

- `references/checklist.md` — the stable `base:<id>` harness checks profiles can OVERRIDE/SUPPRESS (the contract surface).
- `references/harness-anatomy.md` — the six components to inspect, what "good" looks like for each, and where to find each in a repo.
- `references/context-split-signals.md` — what belongs in static (always-on) vs dynamic context, and the rot signatures (over-stuffed always-on file, stale rules, skills that should be dynamic).
- `references/failure-mode-catalog.md` — symptom → likely missing harness piece, for the "diagnose a failing agent" path.
- `references/advisory-report-template.md` — the FP-suppression gauntlet, the component scorecard, severity definitions, and the deliverable shape.
