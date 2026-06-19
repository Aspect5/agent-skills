# agent-skills — instructions for agents

This private repo is the **source of truth** for a portable set of **project-agnostic Codex skills** for large, quality-critical codebases. Agents pull this repo for context and **replicate the skills onto the local machine**, then tailor them per-project at runtime.

## What's here
- `base/skills/<skill>/` — the project-agnostic skills (`SKILL.md` + `references/` + `scripts/` + `agents/openai.yaml`). **The source of truth. Never edit these per-project.**
- `profiles-template/` — a generic profile template to copy into a project.
- `install.sh`, `link-profiles.sh` — bootstrap helpers.

## To replicate the skills onto THIS machine
```bash
./install.sh            # symlink base/skills/* into $CODEX_HOME/skills (default ~/.codex/skills)
./install.sh --copy     # standalone COPY instead — survives the repo moving/being deleted
```
Existing real dirs of the same name are backed up to `~/.codex/skills/.superseded/` first. **Restart Codex** to pick up the skills. Do **not** touch `~/.codex/skills/.system` (preinstalled system skills). Security skills (`security-best-practices`, `security-threat-model`) come from upstream `openai/skills` — install those with `$skill-installer`, not from here.

## To tailor a skill to a project (no fork)
Each base skill is **pure process**; project-specific facts are **data it reads at runtime** (it discovers `AGENTS.md`/`CLAUDE.md`, lint/test/CI config, and an optional profile). To specialize a skill for a project:

1. In the **project's own (private) repo**, create `.agents/profiles/<skill>.md` — copy `profiles-template/<skill>.md` and fill it in.
2. Use `ADD` (new rules), `OVERRIDE base:<id>` (rebind a default), `SUPPRESS base:<id>` (drop a check), plus the `model` / `budget` / `fan_out` knobs.

> **Confidentiality rule:** proprietary/stack-specific details belong **only** in the project repo's profile (and its `AGENTS.md`/`CLAUDE.md`) — **never** in this `agent-skills` repo. The base skills never hardcode a stack; they read it from the project at runtime. Keep this repo stack-agnostic so it stays safe to share across projects.

## If you edit a base skill
Keep it project-agnostic. `description` must stay a 3-part routing contract (what + "Use when" + "Do not trigger for"); body < 500 lines (depth in `references/`); scripts self-root via `git rev-parse` and take `--json`. A base improvement reaches projects on their next pull — so a change here must be safe for *every* consuming project.
