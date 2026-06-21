# Hook mechanisms — wiring a guardrail to each harness

How to install a deterministic check at the right lifecycle point, per harness,
stack-agnostically. The check is the same `scripts/guardrail_check.py` (or your
own script) in every case — only the **wiring** and the **exit-code semantics**
differ. The Agent = Model + Harness; a guardrail lives in the *harness* half, which
is why it cannot be skipped by the model.

> Only load this file when wiring. Copy the snippet for the resolved harness;
> adapt paths to the repo. Every wired invocation must be self-rooting and
> POSIX-portable (`base:portable-self-rooting`).

## The universal exit-code contract

Every harness below honors the same convention, which is why one script serves all:

| Exit | Meaning | Effect at the lifecycle point |
|---|---|---|
| `0` | allow | the action proceeds |
| non-zero | **block** | the tool call / commit / job is stopped; stderr shown |

Fail-closed (`base:fail-closed`) means the script returns non-zero on its *own*
errors too — so a broken guardrail blocks rather than waves things through.

---

## 1. Claude Code hooks (pre-tool — stops the agent before it acts)

The only layer that can block a destructive command or a protected-branch push
**before** the agent runs it. Configured in `.claude/settings.json` (shared) or
`.claude/settings.local.json` (per-machine). The `PreToolUse` hook receives the
tool name + input on stdin and **a non-zero exit blocks the tool call**.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$(git rev-parse --show-toplevel)/.agents/guardrails/guardrail_check.py\" --mode pre-tool --stdin"
          }
        ]
      }
    ]
  }
}
```

- `matcher` scopes the hook to the tool whose calls carry the danger signal (`Bash`
  for command surfaces; a write tool for protected-path surfaces).
- The script reads the tool input from stdin (`--stdin`) and dispatches to the right
  mode (destructive-command / protected-branch).
- **Exit semantics:** non-zero blocks and the stderr message is surfaced to the
  agent — make it actionable (`base:actionable-block`).
- **Bypass:** none from the model side — this is the agent harness itself. It does
  **not** cover a human running the command directly outside the agent; pair with a
  git hook + CI for that.

## 2. git pre-commit hook (catches content before it enters history)

For secrets, large files, banned tokens. Two ways to install — the **pre-commit
framework** (portable, shared via a committed config) is preferred over a raw
`.git/hooks` shim (per-clone, not shared, easy to forget).

### Preferred: `.pre-commit-config.yaml` (framework, shared in-repo)

```yaml
repos:
  - repo: local
    hooks:
      - id: guardrail-secrets
        name: block secrets
        entry: python3 .agents/guardrails/guardrail_check.py --mode secret --staged
        language: system
        pass_filenames: false
        always_run: true
```

`pre-commit install` wires it into `.git/hooks/pre-commit`. Non-zero aborts the
commit. Shared because the config is committed; every contributor who runs
`pre-commit install` gets it.

### Fallback: raw `.git/hooks/pre-commit` shim (no framework available)

```sh
#!/bin/sh
# Self-rooting, POSIX. Non-zero exit aborts the commit.
root="$(git rev-parse --show-toplevel)" || exit 1
exec python3 "$root/.agents/guardrails/guardrail_check.py" --mode secret --staged
```

- `#!/bin/sh` + POSIX only (no `bash` arrays, no `[[ ]]`, no `<<<`).
- **Bypass:** `git commit --no-verify` skips it, and a fresh clone has no
  `.git/hooks` until installed → **a CI backstop is mandatory** for any surface that
  must actually hold (secrets, license). Document the local hook as best-effort.

## 3. git pre-push hook (last local line before a push leaves)

For protected-branch / force-push surfaces when you want a git-native layer in
addition to the agent pre-tool gate. `.git/hooks/pre-push` receives ref updates on
stdin; non-zero aborts the push.

```sh
#!/bin/sh
root="$(git rev-parse --show-toplevel)" || exit 1
exec python3 "$root/.agents/guardrails/guardrail_check.py" --mode protected-branch --pre-push
```

Same `--no-verify` bypass caveat → **server-side branch protection is the
authority**; this is the convenience layer.

## 4. Codex / generic tool-gate harness

Codex-style harnesses expose a command/tool approval hook. The mechanism name
differs but the contract is identical: a configured command runs before the tool,
**non-zero blocks**. Wire the same script in `--mode pre-tool --stdin` (or read the
command from the harness's documented env var, e.g. `--command "$TOOL_COMMAND"`).
If the harness's config format is unknown, **ask the user once** for the hook
registration syntax rather than guessing — a guardrail wired wrong is worse than
none (`base:wired-to-harness`).

## 5. CI / pre-merge (the non-bypassable backstop)

No local `--no-verify` and no missing-local-hook can skip CI — this is the
authoritative layer for any surface that must hold repo-wide. GitHub Actions shown;
the same shape applies to GitLab CI, CircleCI, Cloud Build (a step that runs the
script; non-zero fails the job).

```yaml
name: guardrails
on: [pull_request]
jobs:
  guardrails:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # full history so range scans work
      - run: python3 .agents/guardrails/guardrail_check.py --mode secret --range "origin/${{ github.base_ref }}...HEAD"
```

- `fetch-depth: 0` so a range scan (base…head) sees the real diff.
- Pin the action to a major version (`@v4`), not `@main` (`base:portable-self-rooting`
  spirit — reproducible CI).
- **For fork PRs:** do not expose secrets to the guardrail job; a content scanner
  needs no secrets, so run it on the untrusted `pull_request` event, not
  `pull_request_target`.

---

## Choosing the layer(s) — the matrix

| Surface | Pre-tool | Pre-commit | Pre-push | CI |
|---|:--:|:--:|:--:|:--:|
| Destructive command | **required** | — | — | — |
| Protected-branch push | **required** | — | optional | server-side |
| Secrets | — | recommended | — | **required** |
| Large files | — | recommended | — | optional |
| License / banned dep | — | optional | — | **required** |
| Protected-path edit | optional | recommended | — | **required** |

"required" = without this layer the guardrail does not actually prevent the action.
High-value surfaces appear in two columns deliberately — that is defense in depth
(`base:fail-closed-bypass-aware`), not redundancy.

## Portability traps (each one breaks a guardrail silently)

- **Absolute paths.** Never hardcode `/Users/...` or a CI checkout path — resolve via
  `git rev-parse --show-toplevel`. A guardrail that only fires on the author's
  machine is no guardrail.
- **`bash`-isms under `/bin/sh`.** No `[[ ]]`, `${var,,}`, arrays, `mapfile`, `<<<`.
  git hooks commonly run under `dash` on Debian/Ubuntu CI images.
- **`sed -i` / `readlink -f`.** BSD (macOS) vs GNU (Linux) differ; avoid in-place
  edits and prefer `python3`/`git` for parsing over `sed`/`awk` extensions.
- **Assumed tools.** Don't assume `jq`, `rg`, or a specific Python in the CI base
  image; `python3` + `git` is the safe floor. Check, or fall back.
- **Exit-code masking.** Never `... | tail` / `... | head` in the wiring — the pipe's
  exit code replaces the check's, and a guardrail that can't return non-zero can't
  block.
