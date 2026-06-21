---
name: design-tradeoff
description: >-
  Produces a structured architecture-decision analysis — ≥3 genuinely distinct
  options scored against weighted quality attributes, with mermaid visuals, a
  reversibility-calibrated recommendation, and an ADR in the project's own
  format. Use when asked to compare architectural options, choose between data
  models / deploy strategies / frameworks, weigh a build-vs-buy or
  rewrite-vs-refactor call, or make any non-trivial design decision where
  structured alternatives beat a single opinion. Do not trigger for:
  implementing an already-decided design, code review of a diff, debugging,
  writing feature code, or general Q&A with one obvious answer.
---

# Design Tradeoff Analysis

## Overview

Turn a fuzzy architectural decision into a defensible one. You generate at least
three genuinely distinct options (real architectures, not strawmen), score them
against the quality attributes that actually matter here, surface the tradeoff
points where improving one attribute degrades another, recommend with explicit
consequences and a named back-out path, and emit an Architecture Decision Record
in the project's own format. The depth of ceremony scales to reversibility: a
two-way-door (easily reversed) decision gets a fast pass; a one-way door gets the
full treatment.

This skill ends at "here is the decision record and the recommendation." It does
**not** implement the decision — that is a separate task the user kicks off.

**Output discipline.** The ADR is the deliverable: write it to a file
incrementally (see Step 8) and emit only a tight summary inline. Never paste the
full record back into the conversation.

**Budget posture.** The lean default is single-pass: one agent does framing,
option generation, scoring, and the record. Parallel analyst/reviewer agents
(Steps 2 and 7) are an **explicit opt-in fan-out** — run a cost preflight and
honor the profile's `fan_out` knob before spawning any.

## Step 0 — Context-Absorption Prelude

Run this before anything else. It is identical across these skills.

1. **Note what is already loaded.** `AGENTS.md` / `CLAUDE.md` (root and nested)
   are typically already in your context — use them; do not re-read blindly.
2. **Read the profile if present:** `.agents/profiles/design-tradeoff.md`. Apply
   its frontmatter knobs (`model`, `budget`, `fan_out`, plus any
   `quality_attributes`, `adr_dir`, `adr_template`) and its
   `ADD` / `OVERRIDE base:<id>` / `SUPPRESS base:<id>` directives against the
   base checklist in `references/checklist.md`.
3. **Resolve project specifics, in precedence order:** profile values →
   introspect the repo (look for `docs/adr/`, `docs/decisions/`, `ARCHITECTURE.md`,
   existing ADRs, `package.json` / `pyproject.toml` / `Makefile` / CI for the
   tech stack) → ask the user **once** if a load-bearing fact is still unknown →
   else fall back to the defaults in this skill. **Never fail for lack of a
   profile** — the base runs unmodified with zero config and better with one.

## Workflow

> **Only load the reference files you need**, and only as a step needs them:
> `references/checklist.md` (base:<id> checks),
> `references/scoring-axes.md` (the quality-attribute catalog + weighting),
> `references/adr-templates.md` (ADR formats + discovery),
> `references/agent-prompts.md` (analyst/reviewer prompt templates).

### 1. Frame the decision

- **Restate the question in one sentence.** Confirm with the user if it is
  ambiguous — a misaimed analysis costs far more than one clarifying question.
- **List the hard constraints** any option must satisfy (3–5 bullets: compliance,
  timeline, team skills, existing infra, SLAs). Constraints eliminate options;
  keep them separate from the scored criteria.
- **Prioritize the quality attributes** that this decision trades against, drawn
  from `references/scoring-axes.md` (correctness, performance/scale, operational
  cost, developer ergonomics, dollar cost, security, evolvability, blast radius,
  migration/transition cost). Pick the 4–7 that genuinely matter here and assign
  each a weight (1–5). Do not score against attributes nobody cares about.
- **Classify reversibility** (this sets the depth budget):
  - **Two-way door** (cheaply reversed — a library choice behind an interface,
    a config default): keep it light. One pass, a small table, a recommendation.
    Say so explicitly and stop early if the answer is obvious.
  - **One-way door** (expensive/irreversible — a public API shape, a data model,
    a storage engine, a wire protocol): full treatment, including Steps 4 and 7.
  - Borderline: treat as one-way. The asymmetry of regret favors more analysis.
- Ground yourself: read the relevant code and `ARCHITECTURE.md` sections so the
  options reflect what already exists, not a greenfield fantasy.

### 2. Generate ≥3 genuinely distinct options

Each option must be a **real, buildable architecture** with a different shape —
not three flavors of the same idea, and never a strawman built to lose.

- **Default (lean):** generate the options yourself. Use distinct *framings* to
  force genuine divergence — see `references/agent-prompts.md` for the framing
  catalog (minimal-change, scale-first, operational-simplicity, optionality,
  buy-don't-build). At minimum cover: the smallest change that works, the
  scale-optimal answer, and the most reversible answer.
- **Opt-in fan-out:** one analyst agent per option for deeper, parallel
  exploration. **Before spawning: run a cost preflight** — state "this is ~N
  subagents at <model>; proceed?" and honor `fan_out` (`allowed` → proceed and
  inform; `ask` → wait for a yes; `never` → stay single-pass). Cap total agents
  at 6 (≤4 analysts + ≤2 reviewers). Each analyst returns: approach name,
  3-sentence summary, sketch (pseudo-code or diagram), implementation outline,
  top-3 risks, top-3 advantages. Prompts: `references/agent-prompts.md`.

If, after framing, one option is genuinely dominant, **say so** and do not
fabricate a contest to fill space. A short "the answer is X because Y;
alternatives considered and rejected" record is a valid output.

### 3. Score against the weighted criteria

- Build the decision matrix: rows = options, columns = the weighted quality
  attributes from Step 1. Score each cell 1–5 with a one-line justification —
  never a bare number. See `references/scoring-axes.md` for anchored scoring
  guidance so "3" means the same thing across cells.
- **The matrix is for transparency, not an oracle.** Compute the weighted total,
  but do not let a 1-point spread decide a one-way-door call — name the
  attributes that actually dominate (Step 4) and reason about those.
- Always include these columns regardless of the project's pet attributes:
  **blast radius** (what breaks if this is wrong), **migration/transition cost**
  (getting from today's state to this option), **reversibility** (cost to undo),
  and **operational cost** (on-call, failure modes, moving parts).

### 4. Sensitivity & tradeoff points (one-way doors)

Skip for clearly two-way-door decisions. Otherwise:

- **Tradeoff points:** name each decision where improving one attribute *degrades*
  another (e.g. "sharding by tenant maximizes isolation but blocks cross-tenant
  joins"). These are where the real cost lives.
- **Sensitivity:** state which assumptions, if wrong, flip the recommendation
  (e.g. "if write volume stays < 1k/s, the simple option wins; the scale option
  only pays off above that"). Tie each to an observable threshold where possible.

### 5. Visualize

Add to the record:

- **One mermaid diagram per option** (or one comparative `graph LR`) showing
  data/control flow — make the structural difference visible, not just prose.
  Required for one-way / borderline doors; for a clear two-way door the weighted
  table alone suffices — don't over-produce (honor the Step-1 depth budget).
- **One weighted comparison table** (the Step-3 matrix, rendered).
- **For a migration/rewrite decision:** a phased rollout / strangler-fig diagram
  showing how you get from current state to the target incrementally.

Keep diagrams legible; a diagram nobody can read is worse than a clear sentence.

### 6. Recommend with explicit consequences

A recommendation is not a vote — it is a commitment with stated costs:

- **The pick**, in one sentence, tied to the dominant attributes from Step 4.
- **What you give up** by choosing it (the honest downside, not a disclaimer).
- **The conditions that flip the choice** — the thresholds from Step 5 restated
  as "revisit this if …".
- **A named back-out path:** how to reverse or contain it if it proves wrong.
- **Where feasible, an executable fitness function** — a test, metric, or assertion
  that fails if the chosen architecture drifts from its premise (e.g. a latency
  budget assertion, a dependency-direction lint, a query-fanout cap). This makes
  the decision *self-policing* rather than a doc that rots.

### 7. Stress-test the recommendation (opt-in, one-way doors)

For a one-way door, harden the record before finalizing. **Cost-preflight and
honor `fan_out`** exactly as in Step 2; cap at 2 reviewers within the 6-agent
budget. Single-pass alternative: do this yourself as an explicit adversarial
self-review section.

- **Red team:** steelman the *rejected* options, attack the recommendation's
  assumptions, find the missing option, name the 5-years-from-now regret.
- **Operations:** assume each option is in production — on-call shape, migration
  path from current state, rollback plan, cost at scale, first thing to break
  under load.
- Fold genuine findings back into the relevant sections (do not bolt on a
  "review" appendix and leave the body stale). If review changes the
  recommendation, change it.

### 8. Emit the ADR (write to file)

- **Discover the format and location** (do not assume): `references/adr-templates.md`
  describes the precedence — existing `docs/adr/` or `docs/decisions/` (match its
  numbering and template exactly) → a `*template*.md` in those dirs → else
  MADR-minimal, and **state in the record** that you fell back to MADR because no
  project convention was found.
- **Write incrementally to the discovered path.** Keep the record under ~500
  lines — a decision record nobody reads wastes the analysis.
- **Human-approval pause before the write** if the project convention is to commit
  records (vs. leave them uncommitted for review): create the file, then **stop**
  and ask before any `git add` / commit / branch / push. Default to *not*
  committing unless asked. Never push to a protected branch on your own.
- **Shell-safety** for any emitted commands: single-quote or heredoc commit
  messages (backticks run command substitution on zsh), check exit codes directly,
  never pipe-mask an exit code.

### 9. Self-check / quality gate

Before presenting, verify every item — fix or call out any miss:

- [ ] ≥3 options are **genuinely distinct real architectures** (no strawman, no
      three-flavors-of-one) — or one option is justifiably dominant and that is
      stated, not faked.
- [ ] Hard constraints are separated from scored criteria; no option that violates
      a hard constraint is recommended.
- [ ] Every matrix cell has a one-line justification, not a bare number.
- [ ] Reversibility is classified and the analysis depth **matches** it (no
      over-ceremony on a two-way door; no under-analysis on a one-way door).
- [ ] Tradeoff points and sensitivity thresholds are named (one-way doors).
- [ ] The recommendation states what you give up, the flip conditions, **and** a
      named back-out path.
- [ ] The weighted table is present; a per-option mermaid diagram is included for
      one-way / borderline doors (a clear two-way door may use a small table alone).
- [ ] The ADR was written to the **discovered** format/location (or MADR-fallback
      is explicitly declared).
- [ ] Any fan-out was cost-preflighted and honored `fan_out`; total agents ≤ 6.
- [ ] No write/commit happened without the approval pause; commands are
      shell-safe.
- [ ] Full record is in the file; inline output is a ≤6-sentence summary + path.

Then present: a ≤6-sentence summary, the file path, the recommended option with
its one-line rationale, and ask which option to pursue (or whether to iterate).
Do not paste the full record inline.

## Guardrails

- Don't invent options to fill space — 3 strong options beat 5 mediocre ones.
- If the right answer is obvious from framing, say so; don't fabricate a contest.
- This skill stops at the record + recommendation. **Do not implement** the
  decision.
- Opus/large-model fan-out is real money: single-pass is the default, fan-out is
  opt-in with a preflight, and the cap is 6 agents.
