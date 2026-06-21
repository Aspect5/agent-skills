# Analyst & reviewer agent prompts (opt-in fan-out)

Used **only** when the user opts into multi-agent fan-out (Step 2 option
generation, Step 7 stress-test). The single-pass default needs none of this — you
play every role yourself. Before spawning any of these: **run the cost preflight**
("this is ~N subagents at <model>; proceed?") and honor the profile's `fan_out`
knob. Cap total agents at **6** (≤4 analysts + ≤2 reviewers); use a large model
(a strong model (Opus / a more capable model-class)) so the alternatives are real.

> Only load this file when fan-out is actually approved.

## Shared context block (prepend to every agent)

```
Decision under analysis: <one-sentence restatement>
Hard constraints (any option MUST satisfy all):
  - <constraint 1> … <constraint 5>
Prioritized quality attributes (weight 1–5):
  - <attribute: weight> …
Reversibility class: <two-way | one-way> door
Existing system (grounding): <relevant modules, ARCHITECTURE.md sections,
  current data model / deploy shape>
Return ONLY your option(s); do not recommend a winner — synthesis happens upstream.
```

## Analyst framings (Step 2)

Spawn one per option (≤4). The *framings* — not the people — guarantee genuine
divergence; pick the 3–4 most relevant to this decision so the options have
different shapes, not different paint.

- **A — Minimal change / time-scarce.** "What is the *smallest* change that solves
  this today? Assume the team's time is the scarcest resource and reversibility is
  free. What do we deliberately not build?"
- **B — Scale-first.** "What is best at 10× today's load? Assume volume/latency is
  the binding constraint. Where is the knee, and what does it cost to get there?"
- **C — Operational simplicity.** "What answer minimizes on-call burden, failure
  modes, and moving parts? Optimize for the 3am page never happening."
- **D — Optionality / future-proof.** "What keeps future pivots cheapest? Optimize
  for reversibility and for not painting us into a corner."
- **E — Buy / don't-build.** "Is there a managed service, library, or existing
  internal system that makes most of this someone else's problem? What's the
  lock-in cost?"

Each analyst returns:
```
Approach name:
3-sentence summary:
Sketch: <pseudo-code or a mermaid diagram>
Implementation outline: <ordered, 4–8 steps>
Top 3 risks:
Top 3 advantages:
Migration from current state: <1–3 sentences>
```

## Reviewer prompts (Step 7, one-way doors only)

Spawn ≤2 with the **draft record** as input.

- **Red team.** "Poke holes. Challenge every assumption in the recommendation.
  *Steelman the rejected options* — for each, give the strongest case it should
  have won. Find the missing option nobody proposed. Name the failure mode the doc
  ignores and the 5-years-from-now regret. Then: does any finding change the
  recommendation? If yes, say which option it flips to and why."
- **Operations.** "Assume each option is in production. For each: what does on-call
  look like, what's the migration path from today's state, what's the rollback
  plan, what's the cost at scale, and what's the *first* thing to break under
  load? Which option is operationally cheapest to live with, and is that reflected
  in the scores?"

Each reviewer returns: per-option critiques, missing options/criteria, questions
the record can't answer, and an explicit "recommendation holds / should change
to <option> because <reason>".

## Synthesis discipline

- Fold **material** findings into the relevant record sections (Steps 3–6) — do
  not append a stale "review" block beside an unchanged body.
- If reviewers converge on a different option, **change the recommendation** — the
  point of the stress-test is to be moved by good evidence.
- Drop reviewer nits that don't change the decision; keep the record tight.
