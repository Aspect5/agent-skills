# bug-swarm checklist (stable `base:<id>` checks)

Each check has a stable id so a project profile (`.agents/profiles/bug-swarm.md`) can
`OVERRIDE base:<id>` (rebind a default) or `SUPPRESS base:<id>` (turn it off). The base
ships these ids; the project rebinds them — neither side ever forks the body.

Only load this file when you need the full check list or are applying a profile.

## Repro gate

- **base:repro-required** — A failing test that reproduces the bug must exist and be
  committed before any fix work. No oracle ⇒ no swarm.
- **base:repro-red-right-reason** — The repro must fail on HEAD *for the bug*, not for
  an import error, fixture typo, or setup mistake. Verify the failure message.
- **base:repro-user-visible** — Assert on user-visible behavior / a public contract,
  not an internal implementation detail that may legitimately change.
- **base:repro-rejected-if-green** — A repro that passes on HEAD is rejected: it does
  not capture the bug.

## Branching & worktrees

- **base:base-branch-resolved** — The working branch is cut from the *resolved* base
  branch (`origin/HEAD` → current branch), never an assumed `main`.
- **base:worktree-isolation** — Every hypothesis runs in its own `git worktree`; the
  user's working tree is never edited.
- **base:scope-constraint** — Each agent has an explicit edit scope; an out-of-scope
  edit is an automatic disqualifier.

## Fan-out / budget

- **base:fanout-cost-preflight** — Before dispatching parallel agents, state the
  subagent count and get approval per `fan_out` (`never` skips fan-out, `ask`
  requires approval, `allowed` proceeds under the budget cap).
- **base:hypothesis-diversity** — The N hypotheses must be distinct root-cause
  families, not N samples of one patch (see `hypothesis-families.md`).

## Overfit guard

- **base:full-suite-green** — The full regression suite must be green on a candidate;
  any newly broken test disqualifies it.
- **base:adversarial-siblings** — 1–2 sibling tests (same bug class, unseen inputs)
  must pass; the patch never sees them before being written.
- **base:no-special-casing** — Reject patches that branch on the repro's literal
  inputs to make it pass.
- **base:no-assertion-weakening** — Reject patches that loosen/delete an existing
  assertion, broaden a `try/except`, comment out a check, or skip/xfail a test to go
  green.

## Selection

- **base:correctness-gate** — Only candidates passing repro + siblings + full suite are
  eligible to win.
- **base:minimal-blast-radius** — Prefer the smallest diff / fewest files / no
  public-contract change.
- **base:no-new-lint-type-errors** — The winner introduces no new lint or type errors.
- **base:tie-break-root-cause** — Break ties on the clearest, most general root-cause
  writeup; use an LLM-judge fix-spec check to catch consensus-overfit.

## Abstain

- **base:abstain-over-guess** — If nothing survives the overfit guard, do NOT ship the
  least-bad patch. Return the repro + ranked hypotheses + failure analysis and mark
  needs-human.

## Ship

- **base:human-approval-before-push** — Pause for approval before any push / PR /
  branch publish.
- **base:gate-pass-literal** — Run the project's own quality gate on the winner and
  report its literal pass line; capture its own exit code (never pipe to
  `tail`/`head`).
- **base:regression-test-real** — The shipped repro/sibling tests fail on the buggy
  code and pass on the fix (a true tripwire, not vacuous coverage).
- **base:worktree-cleanup** — All losing worktrees are removed; the winner is kept
  until merge.

## Guardrails

- **base:scope-local-no-schema** — Never autonomously change migrations, DB schema,
  auth/security contracts, or public API shapes to make a test pass; escalate instead.
- **base:no-protected-branch-commit** — Never commit directly to a protected branch.
- **base:shell-safety** — Single-quote/heredoc commit messages; check exit codes
  directly; never pipe-mask an exit code.
