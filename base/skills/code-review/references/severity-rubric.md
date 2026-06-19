# Severity rubric, FP-suppression gauntlet, and report template

The part of the skill that turns candidate observations into a trustworthy, low-noise review. A review's value is its **precision**: ten findings where two are wrong trains the reader to ignore all ten. Bias toward fewer, higher-confidence findings and toward approval.

> Only load this file when assigning severity, running the gauntlet, or formatting the report.

## Severity definitions

| Severity | Marker | Definition | Merge implication |
|---|---|---|---|
| Blocker | 🔴 | A correctness, security, data-loss, or contract bug that will cause a real failure or regression in production or in CI. Reproducible or provable. | Must fix before merge. |
| Should-fix | 🟠 | A real defect or risk that should be addressed but isn't a guaranteed failure (edge case, missing test for a real branch, a should-be-handled error path, a maintainability trap with concrete cost). | Fix or consciously accept. |
| Nit | 🟡 | A minor, optional improvement with no behavioral risk. Cap at ≤5 inline; summarize the rest as a count. | Author's discretion. |
| Pre-existing | 🟣 | A real issue you noticed while grounding, but in code the diff did NOT change. | Muted — do not block the diff; note separately. |

Every finding carries a **confidence** (high / medium / low). A low-confidence blocker is a contradiction — either prove it to high confidence or downgrade it. At full tier, blockers and should-fixes must clear the independent-verifier refutation pass (below).

**Severity recalibration:** if the ProjectProfile asks for it (e.g. "missing RLS = blocker"), apply the project's bump/demote. Otherwise use the table as-is.

## The FP-suppression gauntlet

Every candidate finding must survive ALL gates before it is reported. Run them in order; the first that fails drops or downgrades the finding.

1. **Prove-the-behavior.** Re-open the cited `file:line` AND its resolved context (callees, callers, the type/init/config sites, the test that covers it). State the concrete artifact that proves the bug: the exact line, a constructed counterexample input, or a check you ran. **No concrete proof ⇒ drop it.** "This looks like it could…" is not a finding.

2. **Already-handled.** Is the concern guarded somewhere the diff doesn't show — an upstream validator, a type that makes the bad state unrepresentable, a caller that already checks, a framework guarantee? If yes, drop it. This is the gate that catches the #1 false-positive cause: judging a changed line without the related files.

3. **Convention / CI-skip.** Does the ProjectProfile's `ci_enforces` list already cover this class (lint, format, import order, types)? Does `accepted_exceptions` bless this pattern? If yes, drop it. **Never re-flag what CI already enforces** — it's pure noise and undermines trust in the whole review.

4. **What-not-to-flag (per-dimension, below).** If the candidate matches a what-not-to-flag entry for its dimension, drop it.

5. **Scope.** Is the finding about a line the diff actually changed? If it's in unchanged code, move it to the 🟣 pre-existing muted tier — don't block the diff on it.

6. **Re-review convergence.** On a re-run of an already-reviewed PR, suppress brand-new nits and anything previously surfaced-and-accepted. Surface only regressions and previously-missed blockers/should-fixes. A review that grows new nits every pass never converges.

### Independent-verifier pass (full tier / fan-out only)

For each surviving blocker and should-fix, run a verifier whose job is to **refute** it: find the guard that makes it safe, the caller that makes it unreachable, or the input domain that makes it impossible. A finding the verifier cannot refute survives at its severity. A finding the verifier refutes is dropped or demoted. This is the single highest-leverage precision tool — use it whenever budget allows.

## What NOT to flag (per dimension)

These are the recurring false-positive patterns. Treat them as hard suppressions, not "use judgment".

- **All dimensions:** changes outside the diff ("you should also refactor X"); style/taste dressed as a bug; anything CI already enforces; speculative "what if requirements change" hooks; duplicate findings (same root cause, different line).
- **correctness:** theoretical edge cases on inputs that are provably constrained upstream; "could be null" when the type/validator guarantees non-null; defensive checks for states that can't occur.
- **security:** defense-in-depth nags where the "attacker-controlled" value is a server constant, env config, or already-authenticated; "this could be exploited if you also did X" chains where X isn't in the diff; flagging the absence of a control the framework already provides; CSRF/XSS notes on endpoints that don't render or accept the relevant content.
- **performance:** micro-optimizations with no measured impact; "this is O(n²)" on inputs bounded to single digits; premature caching suggestions.
- **tests:** demanding tests for trivial getters/pass-throughs; asking for 100% coverage; flagging missing tests for code the diff didn't change.
- **design-system:** any token/spacing/a11y nag when no style doc exists in the profile (the dimension shouldn't have fired); personal aesthetic preferences not in the doc.
- **docs-consistency:** wording/tone/clarity edits with no factual claim; structure preferences (bullets vs prose); whitespace/ordering changes in an otherwise-correct section.
- **platform-portability:** flagging GNU-only constructs in a script the profile says only ever runs on the GNU/Linux CI image; pinning nags on first-party major-version-pinned actions (`@v4` is fine).

## Report template

Lead with the tally and verdict. Write the full report to a file when it exceeds a short summary; emit only the inline summary in chat.

```markdown
# Code review — <scope label>

**Verdict:** <Approve / Approve with should-fixes / Request changes> — <one sentence>.
**Tally:** 🔴 N blockers · 🟠 N should-fix · 🟡 N nits (+M summarized) · 🟣 N pre-existing (muted)
**Tier:** <trivial|standard|full> · **Dimensions run:** <correctness, security, …>

## 🔴 Blockers
- **`<file>:<line>`** (confidence: high) — <issue>. Impact: <what breaks>.
  ```suggestion
  <minimal fix>
  ```

## 🟠 Should-fix
- **`<file>:<line>`** (confidence: …) — <issue>. <why it matters>.

## 🟡 Nits  (showing ≤5; +M more summarized)
- **`<file>:<line>`** — <minor improvement>.

## 🟣 Pre-existing (muted — not introduced by this diff)
- **`<file>:<line>`** — <issue> (out of scope for this review).

## Coverage notes
- correctness: <1 line — what was checked / nothing found>
- security: <1 line, or "narrow scope: secret/URL scan only" on tests-only, or "N/A">
- api-contract: <1 line, or "N/A — no public shape changed">
- data-migrations: <1 line, or "N/A — no migrations">
- performance: <1 line, or "N/A">
- tests: <1 line — mode + what was checked>
- design-system: <1 line, or "N/A — no style doc / no frontend">
- docs-consistency: <fraction of claims verified, e.g. "12/12 paths, 4/4 symbols", or "N/A — code PR">
- platform-portability: <1 line, or "N/A — no CI/build files">

_Generated by the code-review skill. Not a substitute for a human review of the change's intent._
```

## Output discipline

- For anything beyond a few findings, write the full report to `code-review-<scope>.md` (repo root or a user-named path) **incrementally** as dimensions complete, and emit only `Verdict + Tally + top blockers + path-to-full-report` inline. This prevents the output-cap failure mode on large reviews.
- Every dimension that ran gets a coverage note, even if it found nothing — silence is not the same as "checked and clean".
- Never paste a secret value, signed-URL signature, JWT, or full token into the report; reference by name and mark "redacted".
