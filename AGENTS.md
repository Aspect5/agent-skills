# agent-skills — instructions for agents

This public repo is the **source of truth** for a portable set of **project-agnostic agent skills for Codex and Claude Code** for large, quality-critical codebases. The `SKILL.md` format is shared between the two harnesses, so the same `base/skills/*` run natively in both. Agents pull this repo for context and **replicate the skills onto the local machine**, then tailor them per-project at runtime.

## What's here
- `base/skills/<skill>/` — the project-agnostic skills (`SKILL.md` + `references/` + `scripts/` + `agents/openai.yaml`). **The source of truth. Never edit these per-project.** (`agents/openai.yaml` is Codex interface metadata; Claude Code reads `SKILL.md` frontmatter directly and ignores it.)
- `vendor/<pack>/` — pinned third-party skill packs plus a checked-in upstream snapshot under `upstream/`. **Never edit `upstream/` by hand; sync it through the adapter script.**
- `scripts/external_skills.py` — sync / validate / export approved third-party skills.
- `profiles-template/` — a generic profile template to copy into a project.
- `install.sh` — collision-safe bootstrap that replicates `base/skills/*` (and approved external packs) into the agent's skills dir.

## To replicate the skills onto THIS machine
```bash
./install.sh                # Codex:       symlink base/skills/* into $CODEX_HOME/skills  (default ~/.codex/skills)
./install.sh --claude       # Claude Code: symlink base/skills/* into $CLAUDE_HOME/skills (default ~/.claude/skills)
./install.sh --no-external  # base skills only — skip approved external packs
./install.sh --copy         # standalone COPY instead — survives the repo moving/being deleted
```
**Collision-safe:** a skill of the same name that isn't ours is reported and **left untouched** — never deleted (pass `--force` to back it up to `.superseded/` and override). Approved external packs are staged into `.generated/external-skills/` and installed alongside the base unless `--no-external` is set. **Restart the agent** to pick up the skills. Do **not** touch `~/.codex/skills/.system` (preinstalled system skills). Security skills (`security-best-practices`, `security-threat-model`) come from upstream `openai/skills` — install those with `$skill-installer`, not from here.

## To tailor a skill to a project (no fork)
Each base skill is **pure process**; project-specific facts are **data it reads at runtime** (it discovers `AGENTS.md`/`CLAUDE.md`, lint/test/CI config, and an optional profile). To specialize a skill for a project:

1. In the **project's own (private) repo**, create `.agents/profiles/<skill>.md` — copy `profiles-template/code-review.md` (the canonical example) and adapt its knobs to your skill.
2. Use `ADD` (new rules), `OVERRIDE base:<id>` (rebind a default), `SUPPRESS base:<id>` (drop a check), plus the `model` / `budget` / `fan_out` knobs.

> **Confidentiality rule:** proprietary/stack-specific details belong **only** in the project repo's profile (and its `AGENTS.md`/`CLAUDE.md`) — **never** in this `agent-skills` repo. The base skills never hardcode a stack; they read it from the project at runtime. Keep this repo stack-agnostic so it stays safe to share across projects.

## If you edit (or add) a base skill
Keep it project-agnostic. `description` must stay a 3-part routing contract (what + "Use when" + "Do not trigger for"); body < 500 lines (depth in `references/`); scripts self-root via `git rev-parse` and take `--json`. A base improvement reaches projects on their next pull — so a change here must be safe for *every* consuming project.

**Run the evals before you finish** (they are the machine gate; see `CONTRIBUTING.md`):
```bash
python3 evals/validate_skills.py    # structural contract
python3 evals/routing/check.py      # trigger-collision regression — add a case for a new skill
```
Scaffold a new skill from `templates/skill-skeleton/`.

## If you edit an external pack
Do not rewrite imported skills into `base/skills/`. Update the pack manifest in `vendor/<pack>/pack.json`, sync the checked-in snapshot with `python3 scripts/external_skills.py sync --pack <pack> --source-root <cloned-upstream>`, then run `python3 scripts/external_skills.py check`. Exported names must not collide with `base/skills/`, and Codex-incompatible top-level frontmatter must be removed or explicitly filtered at the adapter seam.
