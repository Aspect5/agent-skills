# Guardrail catalog — danger surface → deterministic check

A library of the recurring danger surfaces and, for each, the deterministic check
that enforces it. Each entry has the **same five fields** — copy this shape when
defining a new surface (Step 1 of the workflow):

1. **Signal** — the observable a deterministic check reads at the lifecycle point.
2. **Lifecycle point** — earliest point that still blocks safely
   (see `hook-mechanisms.md`).
3. **Check** — what the script actually does (`scripts/guardrail_check.py` already
   implements the starred ★ modes).
4. **False-block set** — the legitimate neighbors that MUST still pass (these become
   the `base:no-false-block` tests).
5. **Bypass / depth** — how it can be evaded and the backstop layer.

> Only load this file while picking or defining a surface. Patterns here are
> starting points, not exhaustive — a profile's `secret_patterns` /
> `destructive_patterns` / `protected_branches` refine them per repo.

---

## ★ Secrets in commits / diffs

- **Signal:** staged file content (or a diff hunk) matches a high-confidence
  credential shape: provider-prefixed keys (`AKIA…`, `ghp_…`, `gho_…`, `sk-…`,
  `xox[baprs]-…`, `glpat-…`), a PEM private-key header
  (`-----BEGIN … PRIVATE KEY-----`), a Google API key (`AIza…`), a JWT-shaped triple,
  or a high-entropy assignment to a `*_KEY` / `*_SECRET` / `*_TOKEN` / `PASSWORD` name.
- **Lifecycle point:** pre-commit (block before it enters history) **AND** CI
  (backstop no `--no-verify` can skip). Defense in depth — secrets are the canonical
  both-layers surface.
- **Check:** scan staged content for the pattern set; entropy threshold for the
  generic assignment case to cut false positives; report **redacted** (`ghp_****`),
  never the value.
- **False-block set:** `.env.example` / `*.sample` placeholders; obvious dummies
  (`sk-xxxxxxxx`, `your-token-here`, `changeme`); test fixtures under an allowlisted
  path that intentionally hold synthetic secrets; documentation showing a *format*.
- **Bypass / depth:** `git commit --no-verify` skips the local hook → CI backstop is
  mandatory for this surface. Already-committed secrets need history scanning + key
  rotation, which is out of scope here (this guardrail is preventive, not forensic).

## ★ Push / force-push to a protected branch

- **Signal:** the target ref of a `git push` (especially `--force` / `--force-with-lease`)
  resolves to a protected branch (profile `protected_branches`, else
  `main` / `master` / `release/*` / `staging` / `production`).
- **Lifecycle point:** pre-tool / pre-command — block the agent **before** the push
  runs (a `pre-push` git hook also works but only for the local user; the pre-tool
  gate covers the agent harness). Server-side branch protection is the true
  authority; this guardrail stops the agent from *attempting* the destructive push.
- **Check:** parse the push command's target ref + flags; block force-push to any
  protected branch; optionally block *any* direct push to a protected branch (PR-only
  policy). `scripts/guardrail_check.py --mode protected-branch` reads the command
  from `--command` or `$CLAUDE_TOOL_COMMAND` / argv.
- **False-block set:** force-push to a personal / feature branch; a normal
  (non-force) push to a non-protected branch; `git push` to a fork remote.
- **Bypass / depth:** the real backstop is server-side branch protection
  (GitHub/GitLab settings) — note in the report that the hook is the agent-side
  layer, not the authority. A command-string parser also cannot see an **implicit**
  target: `git push -f` with no refspec (relying on the upstream tracking branch)
  carries no `main` token to match, so a pure pre-tool parser allows it. Cover that
  case at the git layer instead — a `pre-push` hook receives the resolved
  destination ref on stdin (`base:earliest-safe-point` may push you one layer later
  for full coverage) — or make server-side protection the authority and document the
  parser as best-effort. Never report the parser alone as a guarantee.

## ★ Destructive / irreversible shell commands

- **Signal:** the command string matches a destructive pattern with a dangerous
  scope: `rm -rf` targeting `/`, `~`, `$HOME`, or a path outside the workspace;
  `git clean -fdx` / `git reset --hard` at repo root with uncommitted work;
  `git checkout -- .` wiping changes; `DROP TABLE` / `DROP DATABASE` / `TRUNCATE`;
  `chmod -R 777`; `dd of=/dev/…`; `:(){ :|:& };:` fork bomb; `curl … | sh`
  (untrusted pipe-to-shell); a `kubectl delete` / `terraform destroy` against a
  non-sandbox context.
- **Lifecycle point:** pre-tool / pre-command — the **only** point that prevents the
  command. After-the-fact is data already gone.
- **Check:** pattern-match the command; for `rm -rf`, resolve the target against the
  workspace root and block only when it escapes the workspace (so `rm -rf ./build`
  passes, `rm -rf /` and `rm -rf ~/Documents` block). `--mode destructive-command`.
- **False-block set:** in-workspace cleanup (`rm -rf ./node_modules`, `rm -rf dist`);
  `git reset --hard` to a commit when explicitly intended *and approved*; a `DROP`
  inside a reviewed migration file (that is `code-review`'s job, not this gate).
- **Bypass / depth:** obfuscation (`r''m`, base64-decoded commands) defeats a regex —
  state the residual risk; the gate raises the bar, it is not a sandbox. True
  isolation is a container/seccomp layer, out of scope.

## Oversized / binary files

- **Signal:** a staged file exceeds a size threshold (default 5 MB) or is a
  disallowed binary type committed to a source tree (model weights, datasets,
  archives) without Git LFS.
- **Lifecycle point:** pre-commit (block before the blob bloats history — removing it
  later requires history rewrite).
- **Check:** for each staged file, `git cat-file -s` the blob; block over the
  threshold unless the path matches an LFS-tracked pattern or an allowlist.
- **False-block set:** files already tracked by Git LFS; allowlisted fixtures /
  golden files the repo intentionally vendors; a documented large asset path.
- **Bypass / depth:** `--no-verify` → CI size check as backstop for repos that care.

## License / banned-dependency / policy

- **Signal:** a new dependency in a lockfile/manifest carries a disallowed license
  (GPL in a permissive-only repo) or is on a banned list; or a banned import/API
  appears in source (a forbidden crypto primitive, a deprecated internal module, a
  `console.log` in production code if the project bans it).
- **Lifecycle point:** pre-commit for fast feedback **and** CI for the authoritative
  gate (contributors without local hooks).
- **Check:** parse the manifest/lockfile diff or grep the staged source for the
  banned token/license; block with the policy reference and the approved alternative.
- **False-block set:** the dependency on an explicit allowlist with a documented
  exception; the banned token inside a test asserting it is banned; a comment
  mentioning it.
- **Bypass / depth:** policy lists drift — the guardrail is only as current as its
  pattern set; note the owner who maintains it.

## Direct edits to protected / generated paths

- **Signal:** a staged change touches a path that must not be hand-edited (generated
  code, vendored trees, a `CODEOWNERS`-locked dir, a frozen-API file).
- **Lifecycle point:** pre-commit or pre-tool (block the write/commit).
- **Check:** match staged paths against the protected-path set; block with the
  regeneration command or the owner to route through.
- **False-block set:** the generator's own output step (which legitimately writes the
  path); an approved override flag.
- **Bypass / depth:** CI re-runs the generator and diffs — the authoritative check
  that the file matches its source.

---

## Defining a new surface

If the request does not fit an entry above, define one by filling all five fields.
**If you cannot name a deterministic Signal** a check can read at a lifecycle point —
if the concern is "the code should be well-designed" or "the response should be
polite" — it is **not a guardrail**: that is non-deterministic behavior for
`eval-author`, or a judgment call for `code-review`. Do not ship a regex that
pretends to enforce a quality bar; say it belongs elsewhere.
