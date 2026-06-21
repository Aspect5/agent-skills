# agent-skills

Public, portable set of best-in-class **Codex skills** for large codebases where code quality is essential. One source of truth, installable on any machine, tailorable per-project by downstream agents **without forking the base**.

## Layout

```
base/skills/           # PROJECT-AGNOSTIC source of truth. Never forked.
profiles-template/     # canonical profile example to copy + adapt per project
evals/                 # machine gate: validate_skills.py + routing/ (run before a PR)
templates/             # skill-skeleton/ — scaffold a new compliant skill
install.sh             # idempotent bootstrap → $CODEX_HOME/skills (symlinks)
skills-lock.json       # which base version each project consumes
CONTRIBUTING.md        # how to add a skill, and the bar it must pass
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

To specialize a skill for a project, author `.agents/profiles/<skill>.md` **in that project's own (private) repo** — copy `profiles-template/code-review.md` (the canonical example) and adapt its knobs to your skill (each skill's knobs are listed in `docs/TAILORING.md`). A profile can `ADD` rules, `OVERRIDE base:<id>` defaults, or `SUPPRESS base:<id>` checks (by stable id), and carries the **budget/model knobs** (`model`, `budget`, `fan_out`) so skills self-throttle.

> **Confidentiality:** proprietary/stack details live **only** in the project repo's profile — never in this repo. That keeps `agent-skills` stack-agnostic and safe to replicate everywhere.

## Skills

### Code-quality skills — work *on* the code

| Skill | What it does |
|---|---|
| `code-review` | Risk-tiered, convention-discovering review with adversarial false-positive suppression |
| `simplify` | Behavior-preserving de-slop / safe refactor with characterization-test anchors |
| `churn-audit` | Relative-churn hotspots + cross-boundary coupling + ownership signal → architectural advice |
| `bug-swarm` | Repro-first, diverse-hypothesis, abstain-don't-guess automated repair (fan-out budget-gated) |
| `design-tradeoff` | ATAM-style options analysis → decision record in the project's own ADR format |
| `docs-refresh` | Evidence-grounded refresh of AGENTS.md / CLAUDE.md / ARCHITECTURE.md |
| `handoff` | Structured session handoff: state / done / remaining / risks / next command |

### Production-substrate skills — install the discipline *into* a repo

These carry best-practice into whatever repo they touch — the substrate the model needs but most repos lack.

| Skill | What it does |
|---|---|
| `eval-author` | Stand up / strengthen a verification suite: deterministic tests **+** LM-judge evals with anchored rubrics, a runnable `evals/` layout, and an honest coverage report |
| `harness-audit` | Advisory audit of a repo's agent harness (rule files, tools/MCP, guardrails, context split, observability) against *Agent = Model + Harness* |
| `spec-author` | Turn a fuzzy ask into a testable spec: problem + non-goals, acceptance criteria as assertions, edge cases, and a criterion→eval handoff |
| `guardrail-author` | Generate deterministic fail-closed guardrails/hooks (secrets, force-push, destructive ops) wired into the harness, each with a fires / doesn't-false-block test |

Security skills (`security-best-practices`, `security-threat-model`) are kept from upstream `openai/skills` — install those via `$skill-installer`, not this repo.

## Conventions every skill follows

- `description` is a 3-part routing contract (what + "Use when" + "Do not trigger for").
- Body < 500 lines; heavy detail in `references/` (relative links; "only load what you need").
- Scripts referenced as `<path-to-skill>/scripts/x.py`; they self-root via `git rev-parse`, support `--json`, exit non-zero on failure.
- Report-heavy skills write the full deliverable to a file and summarize inline (output-token guard).
- Multi-agent fan-out is explicit opt-in with a cost preflight + `fan_out` cap.
- Human-approval pause before any write/destructive/spend step.

These conventions are **machine-enforced**, not just documented.

## Quality gate (evals)

The contract above is only real if it's checked. Two stdlib-only evals gate every change —
run both before a PR (see `CONTRIBUTING.md`):

```bash
python3 evals/validate_skills.py    # structural: frontmatter, 3-part description, <500-line body,
                                    # every references/ link resolves, every base:<id> is defined,
                                    # scripts compile + take --json, agents/openai.yaml present
python3 evals/routing/check.py      # routing: every known trigger-collision seam stays disambiguated
```

## License

[MIT](LICENSE) © Peter Seelman. Replicate, adapt, and redistribute freely; keep the notice.
