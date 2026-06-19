# PR + diagnosis templates

Use these when shipping a winner or handing back an abstain. Fill every section — an
empty section is a smell. Single-quote/heredoc any commit message; never let a backtick
run command substitution.

Only load this file at Workflow Step 7 (ship / hand back).

## Winner PR

Title (Conventional Commits): `fix(<scope>): <user-visible symptom>`

```markdown
## Summary
<1-2 sentences: the symptom, and what the fix does at a high level.>

## Root cause
<The winning agent's diagnosis: the actual defect and why it produced the symptom.
Name the root-cause family. Cite file:line.>

## Test plan
- New repro test: `<path>` — fails on the buggy code, passes on the fix.
- Adversarial siblings: `<path(s)>` — same bug class, unseen inputs.
- Full suite: <literal pass line from the project's own gate, e.g.
  `pytest -q (1185 passed)` or `vitest run (412 passed)`>.

## Alternatives considered
- <Hypothesis A> — rejected because <overfit / broke siblings / larger blast radius>.
- <Hypothesis B> — rejected because <...>.

## Evidence
<Trace / log / data citation that grounded the diagnosis.>
```

Suggested commands (adapt to the resolved base branch and auth state):

```bash
# from the winning worktree, after the gate passes:
git push -u origin "bug-swarm/<slug>"
gh pr create --base "<resolved-base>" --title 'fix(<scope>): <symptom>' --body-file bug-swarm-<slug>.md
```

If `gh` is not authenticated, emit the branch name, `git format-patch <base>..HEAD`
output, and the exact push/PR commands for the user to run — do not block on auth.

## Abstain: draft diagnosis-only PR

When no candidate survives the overfit guard, the bug must not vanish. Open a **draft**
PR carrying the repro so it stays visible.

Title: `diagnosis(<scope>): <symptom> (no verified fix yet)`

```markdown
> Draft — repro committed, no fix shipped. Needs human.

## Symptom
<user-visible behavior + expected.>

## Reproduction
- Failing test: `<path>` (committed) — red on HEAD for the right reason.
- Steps / inputs: <...>

## Hypotheses tried (ranked)
1. <Family> — <what was attempted> — failed because <broke siblings / overfit /
   didn't move the repro>.
2. ...
3. ...

## Localization
<blame / pickaxe / coupling findings — where the fix most likely lives.>

## Proposed next step
<A different hypothesis set, deeper instrumentation, or the specific question that
would unblock a fix.>

## Evidence
<Trace / log citation.>
```

Mark the PR with the project's needs-human signal (label or a `### Requires human
action` section) so it routes to a person.
