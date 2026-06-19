# Handoff quality checklist

Stable `base:<id>` checks. A project profile (`.agents/profiles/handoff.md`) can
`OVERRIDE base:<id>` (rebind a default) or `SUPPRESS base:<id>` (turn a check off) by id, and
`ADD` project-specific checks. The base body's Step 8 self-check gates on the items below; this
file is the canonical, override-addressable copy.

Only load this file when you need the full id list (e.g. when applying a profile or debugging
why a self-check fired).

## Content completeness

- **base:has-current-state** — The handoff states the current branch, deploy/PR status, and
  the dirty-file set. Evidence: matches `git rev-parse --abbrev-ref HEAD` + `git status --short`.
- **base:has-completed-with-evidence** — A "Completed" section lists each finished item with a
  concrete proof (commit SHA, PR URL, `file:line`, or passing-check line).
- **base:has-remaining-ordered** — A "Remaining" section lists outstanding work in execution
  order (dependencies first), each item naming target file(s) and the intended change.
- **base:has-open-risks** — An "Open risks / blockers" section names what could bite the next
  session (failing/flaky checks, unmerged stacked PRs, schema/migration state, deferred human
  decisions, env/secret coupling), each with a mitigation or the open question.
- **base:has-next-command** — An "Exact next command(s)" section exists and is non-empty.

## Verifiability

- **base:every-claim-has-proof** — No "completed" claim is asserted without evidence; anything
  unbackable is dropped or downgraded to "needs verification".
- **base:state-matches-git** — Branch, dirty files, and listed commits match the actual
  `git status --short` / `git log` captured in Step 1 (no stale or hallucinated state).
- **base:pinned-shas** — Where reproducibility matters, the doc pins `HEAD` and the
  `merge-base` SHAs so it stays valid after the base ref moves.
- **base:gh-claims-grounded** — Every PR/CI claim is backed by real `gh` output; if `gh` was
  unavailable/unauthenticated, the doc says so and omits the claim rather than guessing.
- **base:next-command-runnable** — The next command(s) are literal and copy-paste runnable,
  resolved from the project (profile → introspection → asked once), never invented.
- **base:no-vague-remaining** — No remaining item says only "continue the work" / "finish the
  refactor"; each is specific enough to act on without re-deriving scope.

## Safety & discipline

- **base:shell-safe-commands** — Emitted commands are shell-safe: single-quote or heredoc
  around backticks / `$()` (zsh runs command substitution inside double quotes), exit codes
  checked directly, no pipe-masked exit codes (e.g. no `gate | tail` when the gate's exit code
  matters).
- **base:no-unapproved-writes** — The skill performed no commit / push / merge / deploy / spend.
  Any such action is surfaced as a command for the next session and left for explicit human
  approval; it is never a side effect of producing the handoff.
- **base:output-discipline** — The full handoff lives in the file; the inline reply is a tight
  summary (state line, top remaining items, top risk, next command) plus the file path — not
  the whole document.
- **base:fan-out-gated** — Any multi-agent reconstruction across branches/PRs/worktrees was an
  explicit opt-in with a cost preflight, honoring the profile's `fan_out` / `budget` / `model`;
  the default path is single-pass with no silent fan-out.
