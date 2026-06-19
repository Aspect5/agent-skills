# agent-skills

Private, portable set of best-in-class **Codex skills** for large codebases where code quality is essential. One source of truth, installable on any machine, tailorable per-project by downstream agents **without forking the base**.

## Layout

```
base/skills/          # PROJECT-AGNOSTIC source of truth. Never forked.
overlays/<project>/    # per-project profile deltas (additive only)
profiles-template/     # starter profile to copy into a new project
install.sh             # idempotent bootstrap → $CODEX_HOME/skills (symlinks)
link-profiles.sh       # per-project: materialize an overlay into .agents/profiles
skills-lock.json       # which base version each project consumes
```

## Replicate onto a machine

Agents pull this repo for context and replicate the skills locally; a human can do the same:

```bash
git clone https://github.com/Aspect5/agent-skills.git ~/src/agent-skills   # public — no auth needed
cd ~/src/agent-skills && ./install.sh          # symlink base skills into ~/.codex/skills
#                        ./install.sh --copy    # OR standalone copies (survive the repo moving)
# then RESTART Codex to pick them up
```

`install.sh` replicates every `base/skills/*` into `$CODEX_HOME/skills` (default `~/.codex/skills`). Symlink mode (default) means one `git pull` updates every machine; `--copy` makes self-contained copies. Existing real dirs of the same name are backed up to `~/.codex/skills/.superseded/` first. See **`AGENTS.md`** for the agent-facing replication + tailoring contract.

Codex-native alternative (one-off, no auth — the repo is public): `$skill-installer install https://github.com/Aspect5/agent-skills/tree/main/base/skills/<skill>`.

## Per-project tailoring (no fork)

Each base skill is **pure process**; everything project-specific is **data read at runtime**. The base skill discovers a project's stack itself (its `AGENTS.md`/`CLAUDE.md`, lint/test/CI config) — it never hardcodes one.

To specialize a skill for a project, author `.agents/profiles/<skill>.md` **in that project's own (private) repo** — copy `profiles-template/<skill>.md` and fill it in. A profile can `ADD` rules, `OVERRIDE base:<id>` defaults, or `SUPPRESS base:<id>` checks (by stable id), and carries the **budget/model knobs** (`model`, `budget`, `fan_out`) so skills self-throttle.

> **Confidentiality:** proprietary/stack details live **only** in the project repo's profile — never in this repo. That keeps `agent-skills` stack-agnostic and safe to replicate everywhere. (`link-profiles.sh` exists only for the rare case of versioning a non-confidential profile centrally; the default home is the project repo.)

## Skills

| Skill | What it does |
|---|---|
| `code-review` | Risk-tiered, convention-discovering review with adversarial false-positive suppression |
| `simplify` | Behavior-preserving de-slop / safe refactor with characterization-test anchors |
| `churn-audit` | Relative-churn hotspots + cross-boundary coupling + ownership signal → architectural advice |
| `bug-swarm` | Repro-first, diverse-hypothesis, abstain-don't-guess automated repair (fan-out budget-gated) |
| `design-tradeoff` | ATAM-style options analysis → decision record in the project's own ADR format |
| `docs-refresh` | Evidence-grounded refresh of AGENTS.md / CLAUDE.md / ARCHITECTURE.md |
| `handoff` | Structured session handoff: state / done / remaining / risks / next command |

Security skills (`security-best-practices`, `security-threat-model`) are kept from upstream `openai/skills` — install those via `$skill-installer`, not this repo.

## Conventions every skill follows

- `description` is a 3-part routing contract (what + "Use when" + "Do not trigger for").
- Body < 500 lines; heavy detail in `references/` (relative links; "only load what you need").
- Scripts referenced as `<path-to-skill>/scripts/x.py`; they self-root via `git rev-parse`, support `--json`, exit non-zero on failure.
- Report-heavy skills write the full deliverable to a file and summarize inline (output-token guard).
- Multi-agent fan-out is explicit opt-in with a cost preflight + `fan_out` cap.
- Human-approval pause before any write/destructive/spend step.
