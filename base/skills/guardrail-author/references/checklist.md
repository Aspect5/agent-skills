# Guardrail-quality checklist (stable `base:<id>` ids)

The contract surface of this skill. Every guardrail it ships must satisfy these
checks; every `base:<id>` named in `SKILL.md` is defined here. A project profile
rebinds or disables a check by id:

- `## OVERRIDE` → `base:<id> → <new rule>` rebinds a check (e.g. a repo that
  permits force-push to a named sandbox branch rebinds `base:scoped-narrow`).
- `## SUPPRESS` → `base:<id>` turns a check off for that project (rare — most of
  these are non-negotiable; suppressing `base:fail-closed` or `base:tested-fires`
  effectively turns a guardrail back into a hope).
- `## ADD` → appends project-specific checks (give them project ids, not `base:`).

> Only load this file when authoring or grading a guardrail. The ids are the
> contract surface — do not rename them. The self-check in `SKILL.md` reports a
> literal result for each id it used; it never asserts a pass it did not observe.

## Determinism — the defining property

- `base:deterministic-not-prompt` — the guardrail is **code that runs at a
  lifecycle point**, not a sentence added to `AGENTS.md` / a system prompt / a tool
  description that the model is asked to remember. The test: could a confused,
  adversarial, or distracted model *skip* it? If yes, it is not deterministic.
  Prompts state intent; hooks enforce it. Things the agent "must never forget"
  belong in a hook precisely because the hook cannot forget. If the only feasible
  enforcement is a prompt instruction (the signal is non-deterministic — quality,
  tone, judgment), this is the **wrong skill**: route non-deterministic behavior to
  `eval-author`, and say so rather than shipping a fake guardrail.

## Fail-closed — the safety direction

- `base:fail-closed` — on **any** internal failure (unreadable input, thrown
  exception, missing dependency, timeout, ambiguous/unparseable target, the check's
  own bug) the guardrail **blocks** (non-zero exit) and explains why on stderr. It
  never allows-on-error. Contract: exit `0` = allow, non-zero = block. This is
  graded by *constructing* a failure (feed the check garbage / an unreadable path)
  and observing it blocks — not by reading the code and assuming.
- `base:fail-closed-bypass-aware` — the guardrail's threat model names how it could
  be bypassed (`--no-verify` on git hooks, an uninstalled local hook, a direct API
  call around the agent) and, for high-value surfaces, pairs the bypassable layer
  with a non-bypassable backstop (CI). A single local-only secret hook is documented
  as best-effort, not as a guarantee.

## Scope — block exactly the danger, nothing legitimate

- `base:scoped-narrow` — the check blocks the named danger and **only** that. It
  honors an explicit allowlist (profile `allowlist`, conventional safe paths like
  `.env.example`, fixture dirs that intentionally hold dummy values). The failure
  mode this prevents: a guardrail so broad it blocks legitimate work, gets disabled
  within a week, and protects nothing. Narrow + kept beats broad + removed.
- `base:actionable-block` — when the guardrail fires, its message states *what* was
  blocked, *why*, and the *escape hatch* (the approved path, an env var, a person to
  ask, or `--no-verify` if that is genuinely acceptable for this surface). A cryptic
  or silent block trains people to bypass; an actionable one is obeyed.

## Tested — proof it works, both directions

- `base:tested-fires` — a test constructs the **bad** input and asserts the
  guardrail **blocks** (non-zero exit / expected reason). The bad input is realistic
  for the surface (a synthetic secret string, a force-push to a protected ref, a
  destructive command). No fires-on-bad test ⇒ the guardrail is unproven ⇒ not done.
- `base:no-false-block` — a test constructs each **legitimate neighbor** (the
  good-but-similar input named in the spec) and asserts the guardrail **allows**
  (exit 0). This is the test that keeps the guardrail alive: it documents and
  defends the block/allow boundary so a future change cannot quietly broaden it.
- `base:synthetic-fixtures` — fixtures for the fires-on-bad test use **synthetic /
  clearly-fake** credentials and throwaway repos — never a real secret, real
  protected branch, or a command that actually mutates anything outside a temp dir.
  A test that leaks a secret or force-pushes for real is itself a danger surface.

## Wired — installed at the right lifecycle point

- `base:wired-to-harness` — the check is **actually installed** at the chosen
  lifecycle point in this repo's real harness (Claude Code hook / git hook /
  pre-commit / Codex gate / CI step), with the **fail-closed exit semantics that
  harness honors** (e.g. non-zero `PreToolUse` blocks the tool call; non-zero
  pre-commit aborts the commit; non-zero CI fails the job). A check that exists but
  is never invoked is dead code, not a guardrail.
- `base:earliest-safe-point` — the guardrail runs at the **earliest** point where
  blocking is still safe and still prevents the action. Destructive-command and
  protected-push surfaces must be pre-tool/pre-command (blocking after the agent ran
  the command is too late); secrets get pre-commit *and* CI.
- `base:portable-self-rooting` — the wired invocation resolves the script via repo
  root (`git rev-parse --show-toplevel`), not a machine-absolute path, and uses only
  POSIX-portable shell so it runs identically on a contributor's machine and the CI
  base image. No `bash`-isms under `/bin/sh`, no `sed -i` BSD/GNU split, no tool
  assumed present that the CI image lacks.
- `base:no-silent-overwrite` — installing the guardrail does not clobber an existing
  hook/config at that point; collisions are surfaced (merged result shown) for the
  human to resolve.

## Approval — never mutate the harness silently

- `base:human-approval-before-install` — authoring the files is autonomous;
  **activating** a guardrail (registering a hook, writing `.git/hooks`, committing
  hook config, pushing a CI workflow) waits for explicit human approval, presented
  with the diff/config and the two test results. Never installed onto a protected
  branch by direct push — open a PR. Emitted commands are shell-safe (single-quote /
  heredoc bodies; exit codes checked directly; never pipe a check to `tail`/`head`).
