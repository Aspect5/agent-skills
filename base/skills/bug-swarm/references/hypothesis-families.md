# Root-cause hypothesis families

The point of the fan-out is *diversity*: N agents must chase **distinct** root-cause
families so the tournament explores the space, not N attempts at the same patch. Pick
the families whose signal matches the evidence; spread N across them. Default N=3
(tunable via `$BUG_SWARM_N` or the profile).

Only load this file when choosing the hypothesis spread.

| Family | Signal that suggests it | Where it usually lives |
|---|---|---|
| **Input / edge** | Fails on empty/null/zero/boundary value; works on the "happy" example; off-by-one in counts/indices/ranges | Validation, parsing, the first/last iteration, default handling |
| **State / ordering / concurrency** | Intermittent / non-deterministic; passes alone fails in suite; depends on prior request; "works on second try" | Caches, shared mutable state, async ordering, races, re-entrancy, retry logic |
| **Contract / schema mismatch** | Producer and consumer disagree on a field's name/type/shape; serialize/deserialize round-trip drops data; a recent type/schema change | DTOs, API request/response models, serialization, DB column ↔ model, event payloads |
| **Logic / algorithm** | Wrong answer on a clearly-defined input; the computation is the bug, not the plumbing | Core algorithm, comparison/sort, math, conditionals, state machine transitions |
| **Lifecycle / resource** | Leaks, double-free/double-close, use-after-teardown, exhausted pool/handles, timeout under load | Connection pools, file handles, subscriptions, cleanup/finalizers, context managers |
| **Config / environment** | Works locally, fails in CI/prod (or vice versa); env-var/flag-dependent; missing-default-in-one-env | Feature flags, env config, build-time vs runtime values, defaults |
| **Boundary / integration** | The bug is at the seam between two layers/services; each side looks correct in isolation | UI↔API, service↔worker, app↔DB, cache↔store, third-party client adapters |

## Rules for choosing the spread

- **Span the stack** when the layer is ambiguous: e.g. one UI/state, one
  service/logic, one data/contract hypothesis. This is the highest-value default for
  cross-layer bugs.
- **Don't double-book a family** unless the evidence strongly points at one — two
  agents in the same family is wasted budget.
- **Both sides of every contract.** A schema/contract hypothesis must check the
  *producer* and the *consumer* — the most common false fix patches only one side and
  the other silently still drifts.
- **Localization is a prior, not a fence.** The blame/pickaxe localization (Workflow
  Step 3) biases which families are most likely, but a hypothesis is allowed to look
  outside it — that's the point of fanning out.
- **Concurrency/state hypotheses need a deterministic repro.** If the bug is
  intermittent, the repro test must force the ordering (inject the sequence, not sleep)
  or it can't serve as the swarm oracle.
