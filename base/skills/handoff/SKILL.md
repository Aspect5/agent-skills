---
name: handoff
description: >
  Produces a precise, verifiable session handoff so the next session or agent resumes with
  zero re-derivation: current state (branch, deploy, dirty files), what was completed (with
  commit/PR/file evidence), what remains (ordered), open risks/blockers, and the exact next
  command(s) to run. Use when asked for a handoff, "what's the state", a next-steps or
  resume prompt, to wrap up or pause a session, to summarize where things stand for another
  agent, or as a closing step another skill invokes. Do not trigger for: in-progress
  implementation or debugging, code review, writing feature code or docs, or a general
  status question that does not ask to hand off / resume work.
---

# Handoff

Produce a structured, evidence-backed session handoff that lets the next session (or agent)
resume with no re-derivation. The deliverable is a short, verifiable document: where things
stand, what is done, what remains, what the risks are, and the exact next command to run.

## Overview

A handoff is a contract with the future. Its value is precision, not prose: every claim must
be checkable (a branch name, a commit SHA, a PR number, a `file:line`, a literal command),
and the "next step" must be runnable as written. Vague handoffs ("continue the work", "finish
the refactor") are failures. This skill gathers verifiable state from git/`gh` and the active
task list, then writes a tight handoff to a file and emits a summary inline.

This skill is read-only by default (introspection only). It never commits, pushes, merges, or
deploys. If the user asks the handoff to *also* commit/push, treat that as a separate write
step gated on explicit approval (see Step 6).

## Step 0 — Context-Absorption Prelude

Before doing anything else, absorb the project's own conventions so this skill runs correctly
with **zero** configuration and *better* with a profile — never failing without one:

1. **Repo guidance already in context.** `AGENTS.md` / `CLAUDE.md` (and any nested,
   path-scoped variants) are typically already loaded. Re-read the relevant parts for
   branch/freshness rules, deploy model, and shell-safety conventions.
2. **Profile, if present.** Read `.agents/profiles/handoff.md` if it exists. Apply its
   frontmatter knobs (`commands`, `model`, `budget`, `fan_out`, `focus_paths`,
   `ignore_paths`) and its `ADD` / `OVERRIDE base:<id>` / `SUPPRESS base:<id>` sections
   against the base checklist in `references/checklist.md`.
3. **Resolve commands** (precedence: profile → introspect → ask once). Where the handoff
   needs a build/test/deploy command to cite as the next step, resolve it from the profile
   first; else introspect `package.json` / `pyproject.toml` / `Makefile` / CI config; else
   ask the user once. Do not invent a command.
4. **Defaults.** With no profile and nothing to introspect, fall back to plain git/`gh`
   introspection and the base template. Never fail for lack of a profile.

## Workflow

> Only load the reference files you need. The full checklist with stable `base:<id>` ids is
> in `references/checklist.md`; the output skeleton is in `references/handoff-template.md`.

1. **Establish ground truth (read-only).**
   Gather verifiable state. Prefer porcelain/scriptable output:
   - `git rev-parse --abbrev-ref HEAD` — current branch.
   - `git status --short` — dirty/untracked files (the working-tree truth).
   - `git log --oneline -20` and `git log --oneline <base>..HEAD` — this session's commits
     vs the base branch (resolve `<base>` from project guidance; commonly `main`/`staging`).
   - `git rev-parse HEAD` and `git merge-base HEAD <base>` — pin SHAs so the handoff is
     reproducible even after the base ref moves.
   - If `gh` is available and authenticated: `gh pr list --head <branch> --json number,title,url,state,mergeStateStatus`
     and `gh pr checks <n>` for any open PR's CI state. If `gh` is unavailable, say so and
     fall back to git-only evidence; do not fabricate PR state.
   - Read the active **task list** (if the harness exposes one): which items are completed,
     in-progress, pending. Cross-check against the commits — a task marked done with no
     corresponding commit/PR is a discrepancy to surface, not to hide.

2. **Reconcile claims against evidence.**
   For every "completed" item, attach a concrete proof: a commit SHA, a PR URL, a changed
   `file:line`, or a passing-check line. Drop or downgrade any claim you cannot back. If the
   working tree is dirty, decide per file whether it is part of the work (mention it) or
   unrelated (note it so the next session does not assume it is theirs).

3. **Order the remaining work.**
   List what is left in execution order (dependencies first), not in the order it came up.
   Each remaining item gets enough specificity that the next agent does not have to
   re-derive it: the target file(s), the intended change, and any non-obvious constraint.

4. **Surface open risks and blockers.**
   Name what could bite the next session: failing/flaky checks, unmerged stacked PRs,
   schema/migration state, half-applied changes, decisions deferred to a human, environment
   coupling, secrets/auth that must be set. For each, state the risk and the mitigation or
   the question that must be answered.

5. **Write the exact next command(s).**
   The single most important field. Give literal, runnable commands (resolved in Step 0),
   not descriptions. Honor shell-safety: single-quote or heredoc anything with backticks or
   `$()` (zsh runs command substitution inside double quotes), check exit codes directly,
   never pipe-mask an exit code (e.g. do not `... | tail` a gate whose exit code matters).
   If the next step is a write/deploy/spend action, mark it clearly so the resumer pauses
   for approval rather than running it blind.

6. **Write the handoff to a file; summarize inline (output discipline).**
   Write the full handoff to a file (default `HANDOFF.md` at repo root, or a path the user
   specifies / the profile sets) using the structure in `references/handoff-template.md`.
   Write incrementally; keep the inline reply to a tight summary (state line, top 3 remaining
   items, top risk, the next command) plus the file path. Do not paste the whole document
   inline. **This skill does not commit, push, merge, or deploy.** If the user explicitly
   asked the handoff to also commit/push the file or land work, present the exact command and
   pause for explicit human approval before running it — never as a side effect of producing
   the handoff.

7. **Budget / fan-out posture.**
   This is a lean, single-pass skill — no fan-out by default. If (and only if) the user asks
   to reconstruct state across *many* branches/PRs/worktrees and wants parallel investigation,
   treat that as opt-in fan-out: do a **cost preflight** ("this is ~N subagents — proceed?")
   and honor the profile's `fan_out: allowed | ask | never`, `budget`, and `model`
   (gpt-5.4 → fewer agents, lean on deterministic git/`gh` introspection; gpt-5.5 → more
   latitude). Never fan out silently.

8. **Self-check / quality gate (run before returning).**
   Open `references/checklist.md` and verify the handoff against **every** `base:<id>` there
   (minus any the active profile `SUPPRESS`es); do not return until all pass. The checklist is
   the single source of truth for what each id means — do not restate the descriptions here.
   The load-bearing few, if you check nothing else: `base:next-command-runnable`,
   `base:every-claim-has-proof`, `base:state-matches-git`, `base:no-vague-remaining`,
   `base:gh-claims-grounded`, `base:shell-safe-commands`, `base:no-unapproved-writes`, and
   `base:output-discipline`. Fix any failure before returning. Then emit the inline summary
   (state line · top 3 remaining · top risk · next command · file path) and nothing more.
