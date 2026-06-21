# Failure-mode catalog — symptom → likely missing harness piece

Most agent failures are **configuration failures**. When the user arrives with a symptom ("the agent keeps doing X") instead of asking for a cold audit, start here: map the symptom to the harness component most likely at fault, gather the evidence that component's `base:<id>` checks need, and confirm before asserting. **This catalog is a hypothesis generator, not a verdict** — a symptom can have several causes; the evidence decides.

> Only load this for the "diagnose a failing agent" path (Workflow step 4). For a cold audit, walk `harness-anatomy.md` instead.

## How to use it

1. Match the user's symptom to a row (or rows) below.
2. Go to the named component in `harness-anatomy.md`, gather the evidence its checks require.
3. Confirm the mapped cause against real evidence (`file:line`, a missing file/tool, a measured signal). Reject the hypothesis if the evidence doesn't hold — and check the *other* plausible cause for that symptom.
4. Write the finding with the symptom, the confirmed cause, and the agent-failure link (`base:failure-traced-to-config`).

## Catalog

### "The agent ignores a rule I clearly wrote."
- **Most likely:** the rule is **not deterministic where it needs to be** — it's a prose request for something a hook should enforce (`base:guardrails-deterministic-not-prose`, `base:guardrails-present-for-danger`).
- **Also check:** the rule is **buried** where the agent doesn't load it (`base:rules-discoverable`); it **contradicts** another rule so the agent picks the other (`base:rules-no-contradiction`); it's **vague/aspirational** and not operationalizable (`base:rules-unambiguous`); it's **drowned** in an over-stuffed always-on file the agent stops attending to (`base:context-no-rot`).
- **Fix owner:** if it should be enforced → guardrail-author builds the hook. If the rule is just badly written/placed → recommend the rule edit (hand the actual edit to docs-refresh or the user).

### "The agent invents its own workflow / uses raw shell instead of the right tool."
- **Most likely:** a **missing tool** — the workflow assumes a capability that isn't wired, so the agent improvises (`base:tools-sufficient`).
- **Also check:** the tool exists but is **mis-described**, so the model can't tell when to use it (`base:tools-described`); a declared **MCP server is broken/unreachable** (`base:tools-mcp-reachable`).
- **Fix owner:** wiring/describing the tool is implementation — recommend it; if a guardrail should also block the raw-shell path, that's guardrail-author.

### "The agent shipped a bad change (committed a secret / force-pushed / broke the build)."
- **Most likely:** an **absent deterministic guardrail** for that exact danger (`base:guardrails-present-for-danger`, `base:guardrails-right-trigger`).
- **Also check:** **permissions too wide** so the destructive action wasn't gated (`base:sandbox-writes-gated`, `base:sandbox-posture-explicit`); a **dangerous tool exposed ungated** (`base:tools-no-dangerous-ungated`).
- **Fix owner:** guardrail-author builds the hook/gate. This audit only diagnoses the gap.

### "The agent gets worse over a long session / forgets earlier instructions."
- **Most likely:** **context rot** — an over-stuffed always-on context dilutes attention, and later/earlier rules get neglected (`base:context-no-rot`, `base:context-split-sound`).
- **Also check:** **skill-shaped knowledge pinned always-on** instead of loaded dynamically (`base:context-skills-dynamic`); **tool-surface bloat** eating the budget every turn (`base:context-tools-bloat`).
- **Fix owner:** recommend extracting dynamic content to skills/references; the extraction is an edit (docs-refresh / the user), not this audit.

### "The agent behaves differently on the same task / is unpredictable."
- **Most likely:** **contradictory rules** or **unclear precedence** across overlapping sources — the agent silently resolves the conflict differently each time (`base:rules-no-contradiction`, `base:context-precedence-clear`).
- **Also check:** **confusable tools** the model disambiguates inconsistently (`base:tools-described`).
- **Fix owner:** recommend reconciling the rules / stating precedence (docs-refresh / the user).

### "The agent does the wrong thing confidently."
- **Most likely:** a **stale rule that actively misdirects** — it names a removed command/renamed path and the agent trusts it (`base:rules-current`).
- **Also check:** a **mis-described tool** that claims to do something it doesn't (`base:tools-described`).
- **Fix owner:** the rule/doc accuracy fix is **docs-refresh**'s job — redirect; this audit flags that the stale rule is causing a harness failure, docs-refresh corrects the prose.

### "We can't tell why the agent failed / failures keep recurring."
- **Most likely:** **no observability** — the run is a black box, so failures can't be attributed to a cause and the same one repeats (`base:observability-present`, `base:observability-failure-attributable`).
- **Also check:** **no drift signal**, so slow regression goes unnoticed (`base:observability-drift-detectable`).
- **Fix owner:** adding tracing/logging is implementation; standing up an eval/regression suite is **eval-author**. This audit flags the absence and redirects.

### "The agent's outputs are technically fine but don't meet the spec / keep missing intent."
- **Most likely:** **specification is the bottleneck** — the rules under-specify the actual desired behavior (`base:rules-unambiguous`, `base:rules-actionable-not-aspirational`).
- **Also check:** there's no **eval** to verify the non-deterministic output against intent (drift signal absent — `base:observability-drift-detectable`).
- **Fix owner:** tightening the spec is a rule edit (docs-refresh / the user); building the eval that checks non-deterministic output is **eval-author**. Tests verify deterministic parts; evals verify the non-deterministic parts — and the missing one here is almost always the eval.

## A note on multi-cause symptoms

The same symptom (especially "ignores a rule" and "behaves unpredictably") routinely has more than one contributing cause. Don't stop at the first match: gather evidence for the top two hypotheses, report the one(s) the evidence supports, and if two genuinely co-occur, rank the fixes by which removes the most agent-failure. Never assert a cause you haven't grounded.
