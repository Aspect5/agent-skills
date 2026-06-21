# Advisory report — gauntlet, severity, scorecard, and template

The part of the skill that turns candidate observations into a trustworthy, low-noise advisory. An audit's value is its **precision**: ten "defects" where three are actually intentional teaches the reader to ignore all ten. Bias toward fewer, higher-confidence findings, and toward respecting choices the team made on purpose.

> Only load this when running the gauntlet, assigning severity, or formatting the report.

## The FP-suppression gauntlet

Every candidate finding must survive ALL gates before it's reported. Run them in order; the first that fails drops or downgrades the finding.

1. **Anchor-the-evidence.** Re-open the cited `file:line`, name the specific missing file/tool, or state the measured signal (e.g. "always-on ≈ 6.1k tokens"). **No concrete anchor ⇒ drop it.** "The setup feels weak" is not a finding.
2. **Present-elsewhere.** Is the "missing" piece actually provided by another component? A capability you flagged as a missing tool may be a documented command; a rule you called vague may be operationalized by a hook; an "absent" guardrail may be a CI gate you didn't look at. If it's covered elsewhere, drop it — judging one component without the others is the #1 false-positive cause here.
3. **Intentional / OVERRIDDEN.** Does the profile OVERRIDE this `base:<id>`, or does the repo's stated intent bless this posture (a deliberately wide sandbox in throwaway CI, a terse-by-design rule file, a shell-only-by-choice workflow)? If yes, drop it. Never flag a posture the team chose on purpose and said so.
4. **Wrong-skill.** Is this actually an application-code bug (→ code-review), a doc factual-drift fix (→ docs-refresh), or a request to *build* a guardrail/eval (→ guardrail-author / eval-author)? If so, note + redirect, don't report it as a harness defect this skill owns.
5. **Names-the-failure.** Can you name the concrete agent-failure this defect causes (drift / ignored-rule / wrong-tool / silent-bad-write / unobservable-failure)? If not (`base:failure-traced-to-config`), it's a style opinion — drop or downgrade.

### Independent-verifier pass (fan-out only)

When fan-out is enabled, run a verifier whose job is to **refute** each blocker/should-fix: find the hook that already enforces it, the command that already provides the capability, or the profile OVERRIDE that blesses it. A finding the verifier can't refute survives at its severity; one it refutes is dropped or demoted.

## Severity definitions

| Severity | Marker | Definition | Implication |
|---|---|---|---|
| Blocker | 🔴 | A harness defect that *will* cause a real, recurring agent-failure with material blast radius — an ungated destructive tool, a wide-open sandbox on a shell-running agent, an absent secret-scan with a rule that assumes one, contradictory must-not rules. | Fix before relying on the agent. |
| Should-fix | 🟠 | A real defect that degrades reliability but isn't a guaranteed high-impact failure — a vague rule, context rot, a mis-described tool, no drift signal. | Fix or consciously accept. |
| Nit | 🟡 | A minor improvement with little behavioral risk (a slightly-long rule file that's still all-relevant, a tidier pointer map). Cap ≤5 inline; summarize the rest. | Author's discretion. |
| Intentional | 🟣 | A pattern that looks like a defect but the profile/repo blessed on purpose. | Muted — note it so the next auditor doesn't re-flag it. |

Every finding carries a **confidence** (high / medium / low). A low-confidence blocker is a contradiction — prove it to high or downgrade it.

## What NOT to flag

Hard suppressions, not "use judgment":
- A wide permission / sandbox the profile OVERRIDEs or the repo explicitly intends (throwaway CI, a sandboxed scratch repo).
- A terse rule file that is terse *because it's complete* — short isn't vague.
- A "missing" tool that's actually a documented command or a `Makefile` target.
- A "missing" guardrail that's actually a CI gate or pre-commit you hadn't opened.
- Application-code quality, doc factual-accuracy, or "you should also build the eval/hook" — those are other skills.
- Generic best-practice nags with no named agent-failure ("you should add more observability" with no symptom and no gap that causes a real failure).
- Re-flagging, on a re-audit, a finding the team already saw and consciously accepted.

## Component scorecard

Score each of the six components: **strong** / **adequate** / **weak** / **absent-or-N/A** (state the reason for N/A). The headline harness score is the honest roll-up, weighted toward the components whose defects cause the failures the user reported. Don't average a 🔴 away — a single ungated-destructive-tool blocker caps the score regardless of how clean the rest is.

| Component | Score | Top defect (anchor) | Agent-failure it causes |
|---|---|---|---|
| Rule files (AGENTS/CLAUDE) | | | |
| Tools / MCP surface | | | |
| Guardrails / hooks | | | |
| Permissions / sandbox | | | |
| Static-vs-dynamic context | | | |
| Observability | | | |

## Report template

Lead with the score and the single best first move. Write the full advisory to a file; emit only the inline summary in chat.

```markdown
# Harness audit — <repo / scope label>

**Posture:** <one line — e.g. "Solid rules, but correctness is left to prose: no deterministic guardrails.">
**Harness score:** <e.g. 6/10> — capped by <the worst component / the blocker, if any>.
**Tally:** 🔴 N blockers · 🟠 N should-fix · 🟡 N nits (+M summarized) · 🟣 N intentional (muted)
**Inventory source:** harness_inventory.py (or stated manual fallback)

## Scorecard
| Component | Score | Top defect | Agent-failure it causes |
|---|---|---|---|
| Rule files | <strong/adequate/weak/N-A> | `<anchor>` | <failure> |
| Tools / MCP | … | … | … |
| Guardrails / hooks | … | … | … |
| Permissions / sandbox | … | … | … |
| Context split | … | … | … |
| Observability | … | … | … |

## 🔴 Blockers
- **`<anchor>`** (confidence: high) — <defect>. Causes: <agent-failure>. Fix: <recommendation> (owner: <this advisory / guardrail-author / docs-refresh / eval-author>).

## 🟠 Should-fix
- **`<anchor>`** (confidence: …) — <defect>. Causes: <agent-failure>. Fix: <recommendation> (owner: …).

## 🟡 Nits  (showing ≤5; +M summarized)
- **`<anchor>`** — <minor improvement>.

## 🟣 Intentional (muted — blessed by profile/repo, do not re-flag)
- **`<anchor>`** — <pattern> (intentional per <profile OVERRIDE / stated intent>).

## Action plan (ordered by agent-failure removed)
1. <highest-leverage fix> — payoff: <reliability gained> · risk: <low/med/high> · first safe step: <…> · owner: <skill>.
2. …

## Leave alone
- <intentional, load-bearing harness choice and why it's right>.

## Coverage notes
- Rule files: <1 line — what was checked / nothing found>
- Tools / MCP: <1 line, or "N/A — no tool/MCP surface">
- Guardrails / hooks: <1 line>
- Permissions / sandbox: <1 line, or "N/A — no agent permission config">
- Context split: <always-on token estimate + verdict>
- Observability: <1 line, or "N/A">

_Generated by the harness-audit skill. Advisory only — no harness files were modified. Fixes are handed off to the owning skill (guardrail-author / docs-refresh / eval-author) or the user._
```

## Output discipline

- For anything beyond a few findings, write the full advisory to `harness-audit.md` (repo root or a user-named path) **incrementally** as each component is scored, and emit only `Score + Tally + top 3 defects + best first move + report path` inline. This prevents the output-cap failure mode on a large harness.
- Every component that was in scope gets a coverage note, even if clean — silence is not "checked".
- Never paste a token, signed URL, or credential found in MCP/hook/permission config into the report; reference by name and mark "redacted".
