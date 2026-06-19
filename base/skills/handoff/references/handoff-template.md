# Handoff document template

Copy this skeleton into the handoff file (default `HANDOFF.md` at repo root, or a path the user
specifies / the profile sets). Fill every section with verifiable detail. Delete a section only
if it is genuinely empty (and say so — "No open risks." beats an absent section). Keep it tight:
a handoff is a contract, not an essay.

Only load this file when you are about to write the handoff.

---

```markdown
# Handoff — <one-line task / session title>

_Generated <ISO-8601 timestamp> · branch `<branch>` · HEAD `<short-sha>` · base `<base>` @ `<base-sha>`_

## Current state
- **Branch:** `<branch>` (forked from `<base>` @ `<merge-base-sha>`)
- **HEAD:** `<full-sha>` — `<last commit subject>`
- **Working tree:** clean — OR — dirty (see below)
- **Deploy / PR status:** <e.g. "PR #123 open, CI UNSTABLE (1 check pending)"> — OR — "no PR"
- **Dirty / untracked files** (from `git status --short`):
  - `path/to/file` — <part of this work | unrelated, pre-existing>

## Completed (with evidence)
- <what was done> — `<sha>` / PR <#n or url> / `path:line` / `<passing check line>`
- <what was done> — <evidence>
> Every line here carries a checkable proof. No proof → it is not "completed".

## Remaining (in execution order)
1. <next thing> — target: `path/to/file`; change: <what + why>; constraint: <non-obvious gotcha>
2. <after that> — target: ...; change: ...
3. <then> — ...
> Ordered by dependency. Each item is specific enough to start without re-deriving scope.

## Open risks / blockers
- **<risk>** — <why it bites> → <mitigation, or the open question / human decision needed>
- **<flaky/failing check>** — <which check, last seen state> → <how to confirm green>
- **<stacked PR / migration / env coupling>** — <state> → <what must happen first>
> If there are none: "No open risks/blockers."

## Exact next command(s)
```bash
# Literal, copy-paste runnable. Resolved from the project, not invented.
# Shell-safe: single-quote/heredoc around backticks or $(); no pipe-masked exit codes.
<command 1>
<command 2>
```
> If the next step writes/deploys/spends, it is marked here as **requires approval** and must
> NOT be run automatically by the resuming session.

## Notes for the resumer (optional)
- <context that is not state but saves the next agent time: a dead-end already ruled out, a
  decision rationale, a link to the relevant ADR/issue/trace>
```

---

## Field discipline

- **Current state** is observed, never assumed — copy it from the Step 1 git/`gh` output.
- **Completed** is the highest-trust section; an unbacked claim corrupts the whole handoff.
- **Remaining** is the second-most-read section; specificity here is what saves re-derivation.
- **Exact next command(s)** is the single most valuable field — if the resumer can run one
  command and be productive, the handoff worked.
- Keep the inline summary to: state line · top 3 remaining · top risk · the next command · the
  file path. The file holds the full document.
