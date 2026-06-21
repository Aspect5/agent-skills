# design-tradeoff base checklist

Stable-id checks a project profile can rebind. A
`.agents/profiles/design-tradeoff.md` can `OVERRIDE base:<id>` to change a
default or `SUPPRESS base:<id>` to turn one off. Do not renumber existing ids —
profiles depend on them.

> Only load this file when you need the id contract (Step 0 directive resolution
> and the Step 9 gate).

## Framing & scope

- **base:restate-question** — The decision is restated in one sentence and
  confirmed if ambiguous before analysis begins.
- **base:hard-constraints** — 3–5 hard constraints are listed and kept *separate*
  from scored criteria. No option that violates a hard constraint is recommended.
- **base:quality-attributes** — 4–7 weighted quality attributes are chosen from
  the catalog (`scoring-axes.md`); none scored that nobody cares about. Profiles
  may pin the set via `quality_attributes` (OVERRIDE this).
- **base:reversibility-class** — The decision is classified two-way vs one-way
  door, and the analysis depth matches the class.
- **base:ground-in-code** — Options reflect the existing system (relevant code +
  `ARCHITECTURE.md` read), not a greenfield fantasy.

## Options

- **base:three-distinct-options** — ≥3 genuinely distinct, buildable
  architectures. SUPPRESS-able only when one option is provably dominant and that
  is stated explicitly (then a short "considered & rejected" record is valid).
- **base:no-strawman** — No option exists only to lose; each is steelmanned.
- **base:cover-the-corners** — The option set spans at least: smallest change that
  works, scale-optimal, most reversible.

## Scoring

- **base:cell-justification** — Every decision-matrix cell carries a one-line
  justification, never a bare number.
- **base:anchored-scores** — Scores use the anchored 1–5 scale in
  `scoring-axes.md` so a "3" means the same thing across cells.
- **base:mandatory-columns** — Blast radius, migration/transition cost,
  reversibility, and operational cost are always scored columns regardless of the
  project's pet attributes.
- **base:matrix-not-oracle** — A <2-point weighted-total spread does not by itself
  decide a one-way-door call; the dominant attributes are reasoned about directly.

## Sensitivity (one-way doors)

- **base:tradeoff-points** — Each attribute-vs-attribute tension is named.
- **base:sensitivity-thresholds** — Assumptions that flip the recommendation are
  stated, tied to an observable threshold where possible.

## Visualization

- **base:per-option-diagram** — For one-way / borderline doors, at least one
  per-option (or comparative) mermaid diagram showing the structural/data/
  control-flow difference. A clear two-way door may rely on the weighted table.
- **base:weighted-table** — The weighted comparison table is rendered in the
  record.
- **base:migration-diagram** — For a migration/rewrite decision, a phased
  rollout/strangler diagram from current → target state.

## Recommendation

- **base:explicit-consequences** — The recommendation states what is given up, not
  just what is gained.
- **base:flip-conditions** — The conditions/thresholds that would flip the choice
  are stated as "revisit if …".
- **base:back-out-path** — A named back-out / containment path is given.
- **base:fitness-function** — Where feasible, an executable fitness function (test,
  metric, lint, assertion) that fails on architectural drift is proposed.
- **base:bias-honest** — The recommendation is honest, not a vote for the most
  fashionable option; rejected options are fairly represented.

## Record & process

- **base:adr-format-discovered** — The ADR format/location is *discovered*
  (`adr-templates.md`), not assumed; MADR fallback is explicitly declared when no
  project convention exists. Profiles may pin via `adr_dir` / `adr_template`.
- **base:output-discipline** — The full record is written to a file; inline output
  is a tight summary + path only.
- **base:approval-before-commit** — No `git add` / commit / branch / push without
  an explicit approval pause; default is to leave the record uncommitted.
- **base:shell-safety** — Emitted commands single-quote/heredoc messages, check
  exit codes directly, never pipe-mask.
- **base:fan-out-gated** — Any multi-agent fan-out ran a cost preflight, honored
  `fan_out`, and stayed within the 6-agent cap.
- **base:no-implementation** — The skill stops at the record + recommendation; it
  does not implement the decision.
