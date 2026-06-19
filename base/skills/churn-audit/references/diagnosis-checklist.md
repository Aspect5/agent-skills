# Diagnosis checklist — why a hotspot keeps changing

Load when diagnosing a top hotspot (Workflow Step 4). Each item has a stable
`base:<id>`. A project profile (`.agents/profiles/churn-audit.md`) can rebind or
silence any item:

```markdown
## OVERRIDE
- base:contract-coordination → also treat our protobuf .proto files as a contract surface
## SUPPRESS
- base:org-ownership          # we deliberately rotate owners; bus_factor=1 is expected
```

For each high-`hotspot_score` file, walk these. Most hotspots match 1–3. Cite the
concrete evidence (a commit, a coupling pair, a diff range) next to each match —
an unsupported match is not a finding.

## Architectural failure modes

- **`base:contract-coordination`** — A contract change forces many coordinated
  edits. Signal: high cross-boundary coupling `degree`; the same shape edited in a
  producer and one or more consumers per change. *Read:* the contract isn't a real
  boundary (no schema/type/version gate). *Target:* introduce or harden the
  boundary (typed schema, versioned event, single owner) so one side can change
  without the other.
- **`base:leaky-abstraction`** — Callers reach past the interface into internals;
  every internal change ripples out. Signal: a "core" module coupled to many
  unrelated callers; churn concentrated at the seam. *Target:* tighten the public
  surface; push detail behind it.
- **`base:duplicate-source-of-truth`** — The same fact (a constant, a mapping, a
  validation rule, a piece of state) lives in two+ places and must be edited in
  lockstep. Signal: two files in different boundaries that always co-change.
  *Target:* single source of truth; derive the rest.
- **`base:mixed-responsibility`** — One file owns several unrelated jobs, so it
  churns whenever any of them changes (a god file). Signal: high commits, high
  complexity, many distinct authors, unrelated subjects in `git log`. *Target:*
  split along the responsibilities that change independently.
- **`base:missing-boundary`** — Logic that should be isolated (domain vs
  transport, domain vs persistence, domain vs operational concerns) is tangled, so
  an operational or transport change edits domain code. *Target:* extract the
  boundary; keep operational/infra churn out of domain modules.
- **`base:state-spread`** — State for one concept is scattered across many
  stores/services/components, so a single conceptual change touches all of them.
  Signal: a feature's files always co-change across layers. *Target:* consolidate
  ownership of that state.

## Test & process failure modes

- **`base:tests-coupled-to-impl`** — Tests churn every time the implementation
  changes shape (not behavior), signalling assertions bound to internals rather
  than contracts. Signal: a test file's `relative_churn` tracks its subject's, with
  no behavior change in the diffs. *Target:* test the contract/behavior; mock at the
  boundary.
- **`base:fix-forward-loop`** — Repeated bug-fix / revert / re-fix commits on the
  same lines. Signal (needs `gh` or commit subjects): `revert`, `fix`, `hotfix`,
  `re-fix` clustering. *Read:* the area is poorly understood or under-tested.
  *Target:* characterization test + a real root-cause fix (consider `$bug-swarm`).
- **`base:thrash-rewrite`** — `churn_ratio ≈ 1` over many commits: code is
  deleted and replaced rather than extended. *Read:* indecision or an unsettled
  design. *Target:* pause and decide the shape (consider `$design-tradeoff`) before
  more churn.

## Organizational failure modes

- **`base:org-ownership`** — `bus_factor: 1` with a knowledge silo, OR a high
  `minor_author_fraction` with no clear owner. *Read:* organizational risk
  independent of code quality. *Target:* assign/clarify ownership, write the area's
  docs/ADR, pair on the next change — not necessarily a refactor.

## The two questions to close every diagnosis

1. **Redo question:** "If we rebuilt this area today, what simpler boundary or flow
   would we choose?" Name it concretely.
2. **Cost question:** Does that cleaner target beat the migration cost + current
   risk? If not, the honest recommendation is **leave it** — say so and explain
   why. Demoting a complex-but-stable file (high refactor risk, low churn payoff)
   is a valid, valuable finding.
