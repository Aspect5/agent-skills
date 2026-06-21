---
name: guardrail-author
description: >-
  Generates DETERMINISTIC guardrails for a repo's danger surfaces —
  pre-commit / pre-tool / CI checks that fail-closed on secrets, protected-branch
  pushes, destructive commands, large files, or a named policy — as hook
  scripts/config wired into the repo's agent harness (Claude Code hooks, Codex,
  git hooks, or CI), each with a test that proves it FIRES on the bad case and
  does NOT false-block the good case. Use when asked to add a guardrail or hook,
  deterministically prevent the agent from doing X, block secrets / dangerous
  commands / force-push to main, enforce a policy "the agent must never forget",
  or harden the harness against one specific failure. Do not trigger for: auditing
  the whole harness for what guardrails are MISSING (use harness-audit — it finds
  the gap, this skill builds the named guardrail); reviewing a diff or PR (use
  code-review); standing up evals for non-deterministic behavior (use eval-author);
  writing runtime application authorization / business logic (that is app code, not
  a harness guardrail); or general Q&A.
---

# Guardrail Author

## Overview

A guardrail is **code that runs at a lifecycle point and fails closed** — not a
sentence in `AGENTS.md` the model is asked to remember. Hooks are the place for
the things the agent must never forget, precisely because a deterministic check
cannot forget, get distracted, or be argued out of blocking. This skill takes one
named danger surface ("never commit a secret", "never force-push `main`", "never
`rm -rf` outside the workspace") and produces three coupled artifacts: (1) the
**check** — a fail-closed script/config, scoped to block *exactly* that danger and
nothing legitimate; (2) the **wiring** — it installed at the right lifecycle point
in this repo's actual harness; and (3) the **test** — a proof it FIRES on the bad
input and a proof it does NOT false-block the good input. No test, no guardrail.

The hard contract: every guardrail this skill ships is deterministic, fail-closed,
narrowly scoped, wired to a real lifecycle point, and proven by both a
fires-on-bad and a passes-on-good test. A guardrail that only blocks in theory, or
that also blocks legitimate work, is a defect — not a guardrail.

> **Output discipline.** Write the scripts/config/test as real files and write the
> wiring + verification report to `guardrail-<surface>.md` incrementally. Emit only
> a tight inline summary (what was blocked, where it is wired, the two test
> results). Never paste a discovered secret value, token, or signing key into the
> conversation or the report — reference it by name and mark it redacted.

## Step 0 — Context-Absorption Prelude

Run this before anything else. Never fail for lack of a profile — fall back to
defaults and run unmodified with zero config.

1. **Notice what's already in context.** `AGENTS.md` / `CLAUDE.md` (root and
   nested, path-scoped) are typically already loaded — use them for the repo's
   stated policies, protected branches, and forbidden actions rather than
   re-reading. A policy written in prose there is exactly the kind of thing this
   skill converts into a deterministic check.
2. **Read the profile if present:** `.agents/profiles/guardrail-author.md`. If it
   exists, apply its frontmatter knobs (`model`, `budget`, `fan_out`,
   `focus_paths`, `ignore_paths`, plus any `protected_branches`,
   `secret_patterns`, `destructive_patterns`, `harness`, `allowlist`) and its
   `## ADD` / `## OVERRIDE base:<id>` / `## SUPPRESS base:<id>` directives against
   the checklist in `references/checklist.md`. A SUPPRESSed `base:<id>` is not
   enforced; an OVERRIDDEN one uses the project's rebinding (e.g. a project that
   permits force-push to a sandbox branch).
3. **Resolve commands and harness** in this precedence, first hit wins:
   profile values → **introspect the repo** — detect which harness is in play and
   how tests run:
   - harness: `.claude/settings.json` / `.claude/settings.local.json` (Claude Code
     hooks), `.codex/` or Codex config, `.git/hooks` + `.pre-commit-config.yaml`
     (git hooks), `.github/workflows` / `cloudbuild*.yaml` / `.gitlab-ci.yml` (CI);
   - test command: `package.json` / `pyproject.toml` / `Makefile` / CI config.

   Use the bundled detector for a deterministic read:
   `python3 "<path-to-skill>/scripts/guardrail_check.py" --detect-harness --json`.
   → **ask the user once** if the harness is still ambiguous (a guardrail wired to
   the wrong lifecycle point is worse than none). → ecosystem default last.
4. **Fall back to defaults** when no profile and no override exist — the skill must
   run with zero config. Honor budget posture from the start: this is a
   single-pass, single-agent skill by default (see Budget & fan-out); a cheaper `model` ⇒ prefer the scripted detector + library patterns over open-ended
   regex authoring; a more capable model ⇒ more latitude to hand-craft a bespoke check.

## Workflow

> Only load the reference files a step needs:
> `references/checklist.md` (the `base:<id>` contract surface),
> `references/guardrail-catalog.md` (danger surface → the deterministic check),
> `references/hook-mechanisms.md` (how to wire each harness, stack-agnostically),
> `references/testing-guardrails.md` (the prove-it-fires + prove-no-false-block
> recipe), `references/report-template.md` (the deliverable shape).

### 1. Name the danger surface precisely (the specification gate)

A guardrail is only as good as the line between "block" and "allow" — that line is
the whole specification, and specifying it is the bottleneck, not coding it.

- State in one sentence the **exact bad action** to block and the **observable
  signal** at the lifecycle point that distinguishes it (an env var, a command
  string, a staged-file content match, a target ref). If you cannot name a signal a
  deterministic check can read, **stop** — the concern may belong in an eval
  (non-deterministic behavior → `eval-author`) or in code review, not a hook.
- State the **legitimate neighbors** that must keep working (the false-block set):
  e.g. blocking `git push --force` to `main` must still allow force-push to a
  personal branch; blocking secrets must still allow an `.env.example` placeholder.
  Write these down now — they become the passes-on-good tests in Step 5.
- Pick the surface from `references/guardrail-catalog.md` (secrets,
  protected-branch, destructive command, large file, license/policy) or define a
  new one with the same five fields the catalog uses.

### 2. Choose the lifecycle point — earliest that fails closed

Map the surface to the **earliest** point where blocking is still safe and the bad
action is still preventable (`references/hook-mechanisms.md` has the per-harness
matrix):

- **Pre-tool / pre-command** (Claude Code `PreToolUse`, Codex tool gate): the only
  point that can stop the agent *before* it runs `rm -rf` or `git push`. Use for
  destructive-command and protected-branch-push surfaces — blocking after the fact
  is too late.
- **Pre-commit** (git hook / pre-commit framework): catches secrets and large files
  before they enter history. Necessary but **not sufficient** for secrets — a
  determined or hook-skipping (`--no-verify`) path needs a CI backstop too.
- **CI / pre-merge** (`.github/workflows`, etc.): the fail-closed backstop that no
  local `--no-verify` can bypass. Use for anything that must hold repo-wide,
  including for contributors without the local hooks installed.
- **Defense in depth:** the highest-value surfaces (secrets) get *both* a local
  fast check and a CI backstop. State which layers you are installing and why.

### 3. Build the check — deterministic, fail-closed, narrowly scoped

Write the smallest check that blocks exactly the named signal:

- **Reuse the reference implementation** where it fits:
  `scripts/guardrail_check.py` is a self-rooting, `--json`, fail-closed scanner with
  built-in `secret`, `protected-branch`, and `destructive-command` modes the
  generated hook can call directly — prefer wiring a hook to it over hand-rolling
  fragile inline regex. Extend it (a new `--mode`) rather than forking it.
- **Fail closed (`base:fail-closed`).** On any internal error — unreadable input,
  a thrown exception, a missing dependency, an ambiguous parse — the check must
  **block and exit non-zero**, never silently allow. A guardrail that fails open is
  not a guardrail. Exit-code contract: `0` = allow, non-zero = block with a clear
  reason on stderr.
- **Scope narrowly (`base:scoped-narrow`).** Block the danger and nothing else.
  Honor an explicit allowlist (profile `allowlist`, `.env.example`, fixture/test
  paths that intentionally contain dummy secrets) so the check does not become the
  thing everyone disables. A guardrail that false-blocks gets removed within a week.
- **Make the block message actionable.** When it fires it must say *what* was
  blocked, *why*, and the *escape hatch* (the approved path, the env var to set, or
  who to ask). A silent or cryptic block trains people to bypass it.

### 4. Wire it to the harness — at the real lifecycle point

Install the check where the resolved harness actually invokes it
(`references/hook-mechanisms.md` has copy-ready wiring per harness):

- Emit the exact config/registration (a `.claude/settings.json` hook entry, a
  `.pre-commit-config.yaml` repo entry, a `.git/hooks/pre-commit` shim, or a CI
  workflow step) that calls the check at the chosen point with a **fail-closed exit
  semantics** the harness honors (e.g. Claude Code: non-zero `PreToolUse` exit
  blocks the tool call; pre-commit: non-zero aborts the commit; CI: non-zero fails
  the job).
- **Self-rooting & portable.** The wired invocation must resolve the script by repo
  root (`git rev-parse --show-toplevel`), not a machine-absolute path, and must use
  only POSIX-portable shell so it runs on a contributor's machine and the CI image
  alike (`references/hook-mechanisms.md` lists the portability traps).
- **Do not silently overwrite** existing hook config. If a hook is already present
  at that point, show the merged result and flag the collision for the human.

### 5. Test both directions — fires AND does-not-false-block (mandatory)

A guardrail with no test is a hope. For each guardrail produce **two** tests
(recipe in `references/testing-guardrails.md`):

- **Prove-it-fires (`base:tested-fires`).** Construct the bad input (a fixture file
  with a synthetic secret, a `git push --force origin main` invocation against a
  throwaway repo, an `rm -rf /` command string) and assert the check **blocks**
  (non-zero exit, expected reason). Use only **synthetic / clearly-fake** secrets in
  fixtures — never a real credential.
- **Prove-no-false-block (`base:no-false-block`).** Construct each legitimate
  neighbor from Step 1 (the `.env.example`, the personal-branch force-push, the
  in-workspace `rm -rf ./build`) and assert the check **allows** (exit 0). This test
  is what keeps the guardrail from being ripped out for being annoying.
- Place tests where the project's tests live, mirroring an existing test's framework
  and runner. Run them with the resolved test command. **Both must pass before you
  claim the guardrail works** — capture the literal pass/fail lines.

### 6. Budget & fan-out posture (cost preflight before any multi-agent run)

**Single-pass, single-agent is the default and needs no preflight** — authoring one
guardrail + its two tests is cheap and deterministic. Multi-agent fan-out is
**opt-in** and only justified when generating a *batch* of independent guardrails
(e.g. "harden every danger surface harness-audit found"):

- Honor the profile `fan_out` knob: `never` → single-pass only; `ask` → state "this
  is ~N subagents, one per guardrail surface — proceed?" and wait; `allowed` →
  proceed but announce the count and cap it at the budget ceiling.
- Honor `budget` and `model`: on a cheaper model or a tight budget, stay single-pass and
  lean on the scripted detector + catalog patterns; on a more capable model with headroom,
  per-surface subagents and bespoke checks are fine. Each subagent owns exactly one
  surface and returns its three artifacts; one synthesis pass dedupes wiring and
  resolves hook collisions.

### 7. Human-approval pause before installing (this repo never mutates silently)

Authoring the files is safe; **installing** a guardrail changes how the harness
behaves for everyone — that is the irreversible, outward step.

- **Pause for explicit approval** before any write that activates a guardrail:
  registering a hook in `.claude/settings.json`, writing into `.git/hooks`,
  committing a `.pre-commit-config.yaml` change, or pushing a CI workflow. Present
  the diff/config and the two test results first, then wait.
- **Never commit or push to a protected branch** to install a guardrail — open a PR.
- **Shell-safety:** single-quote or heredoc any emitted command/config body
  (backticks run command substitution on zsh); check exit codes directly; never
  pipe a test or check to `tail`/`head`, which masks the exit code the guardrail's
  whole contract depends on.

### 8. Self-check / quality gate (final word)

Before declaring done, verify every box and **report the literal results — never
assert**. Every `base:<id>` this skill used must be honored:

- [ ] **`base:deterministic-not-prompt`** — the guardrail is code at a lifecycle
      point, not an instruction added to `AGENTS.md`/a prompt. (If the only output
      is prose for the model to follow, this is the wrong skill — say so.)
- [ ] **`base:fail-closed`** — verified the check **blocks** (non-zero) on an
      internal error / unreadable input, not just on the happy bad-case. Paste the
      error-path result.
- [ ] **`base:scoped-narrow`** — the check blocks only the named danger; the
      allowlist is honored; no legitimate neighbor is caught.
- [ ] **`base:tested-fires`** — the prove-it-fires test exists and **passed**
      (the check blocked the bad input). Paste the literal line.
- [ ] **`base:no-false-block`** — the prove-no-false-block test exists and
      **passed** (the check allowed every legitimate neighbor). Paste the line.
- [ ] **`base:wired-to-harness`** — the check is wired at the chosen lifecycle
      point with the correct fail-closed exit semantics for that harness; the
      wiring is self-rooting and POSIX-portable; no existing hook was silently
      overwritten (`base:no-silent-overwrite`, `base:portable-self-rooting`).
- [ ] **`base:earliest-safe-point`** — the guardrail runs at the **earliest** point
      where blocking is still safe and still prevents the action (pre-commit / pre-tool
      over post-hoc); state where it fires and why that is the earliest safe point.
- [ ] **`base:fail-closed-bypass-aware`** — the threat model names how the guardrail
      can be bypassed (`--no-verify`, an uninstalled local hook); for a high-value
      surface (secrets, license) a non-bypassable backstop (a CI gate) is installed,
      not only a skippable local hook — paste the CI layer.
- [ ] **`base:actionable-block`** — when the check fires, its message states *what*
      was blocked, *why*, and the *escape hatch* (the approved path / a person to
      ask), not a bare "denied".
- [ ] **`base:human-approval-before-install`** — nothing was installed/committed
      without the approval pause; no protected branch was touched; commands are
      shell-safe.
- [ ] **`base:synthetic-fixtures`** — no real secret value was pasted anywhere;
      fixtures use synthetic, known-non-live credentials.
- [ ] Full wiring + results are in `guardrail-<surface>.md`; only a summary is
      inline.

If any box fails, fix it or do not claim the guardrail is installed. A guardrail
reported as working but unproven is the failure mode this skill exists to prevent.

## Guardrails

- **Deterministic only.** This skill produces code at a lifecycle point. If a
  concern can only be expressed as "the model should try to…", it is not a
  guardrail — route it to `eval-author` (non-deterministic behavior) or leave it as
  a prompt, and say so explicitly.
- **Fail closed, always.** Ambiguity, errors, and missing inputs block. Never ship a
  check that allows-on-error.
- **Prove both directions.** No guardrail is "done" without a passing fires-on-bad
  AND a passing passes-on-good test.
- **Never install silently.** Activation waits for human approval; protected
  branches get a PR, never a direct push.
- **Never leak a secret.** Redact discovered secrets by name; fixtures are
  synthetic; the scanner reports matches redacted.
- **Don't widen scope to feel safe.** A guardrail that blocks legitimate work is a
  defect that gets disabled — narrow beats broad.

## References

Load only the reference files you need:

- `references/checklist.md` — the stable `base:<id>` guardrail-quality checks
  profiles can OVERRIDE/SUPPRESS.
- `references/guardrail-catalog.md` — common danger surfaces, each mapped to its
  deterministic check, signal, lifecycle point, and false-block set.
- `references/hook-mechanisms.md` — how to wire each harness (Claude Code hooks /
  git hooks / pre-commit / Codex / CI), with exit-code semantics and portability
  traps, stack-agnostically.
- `references/testing-guardrails.md` — the prove-it-fires + prove-no-false-block
  recipe, fixture discipline, and synthetic-secret patterns.
- `references/report-template.md` — the wiring + verification report shape.
