# Quality-attribute catalog & weighting

The scored side of a tradeoff. Constraints eliminate options; **attributes** are
where surviving options trade against each other. Pick the 4–7 that genuinely
matter for *this* decision and weight each 1–5. Scoring against attributes nobody
cares about is noise.

> Only load this file for Steps 1 and 3.

## The catalog (ISO/IEC 25010 + operational reality)

Pick from these; a profile may pin a fixed set via `quality_attributes`.

| Attribute | The question it answers | Typical weight driver |
|---|---|---|
| **Correctness / data integrity** | Can this option be *wrong* in a way that corrupts state or returns bad answers? | Almost always high; financial/medical/auth → 5. |
| **Performance / scalability** | How does it behave at 10× today's load? Where's the knee? | High when growth or latency SLAs bind. |
| **Operational cost** | On-call burden, failure modes, moving parts, observability. | High for anything always-on. |
| **Developer ergonomics / evolvability** | Cost to understand, change, and extend it next quarter. | High for code touched often. |
| **Dollar cost** | Infra + license + headcount to build and run. | High under a hard budget. |
| **Security / attack surface** | New trust boundaries, secrets, blast radius of a breach. | High for anything internet-facing or multi-tenant. |
| **Blast radius** | If this is *wrong*, how much breaks? (Always score this.) | Always include. |
| **Migration / transition cost** | Effort + risk to get from today's state to this option. | Always include for non-greenfield. |
| **Reversibility** | Cost to undo it later. (Drives the depth budget too.) | Always include. |
| **Time-to-first-value** | How soon does the team get a usable result? | High under timeline pressure. |
| **Team fit** | Does the team already know this stack / pattern? | High for small/junior teams. |
| **Vendor / lock-in** | How coupled to one provider; exit cost. | High for strategic infra. |

**Always-included columns** (regardless of the project's pet attributes):
correctness, blast radius, migration/transition cost, reversibility, operational
cost. These are the ones teams most often forget and most often regret.

## Anchored 1–5 scale

Use the same anchors in every cell so scores are comparable. Higher = better for
this option on this attribute.

- **5 — Excellent.** Best-in-class for this attribute; a genuine strength of the
  option. No realistic concern.
- **4 — Good.** Comfortably above the bar; minor caveats.
- **3 — Adequate.** Meets the need; no advantage, no real liability.
- **2 — Weak.** Below the bar; works but with notable, named friction or risk.
- **1 — Poor.** A real liability on this attribute; would need mitigation to ship.

Each cell records a **score + a one-line justification** (`4 — caches the hot path
so p99 stays under 50ms at 10×`). A bare number is rejected by the Step-9 gate.

## Weighting & totals

1. Assign each attribute a weight **1–5** by how much it matters *to this
   decision* (5 = decisive, 1 = tiebreaker-only).
2. Weighted total = Σ(weight × score). Render both the raw cells and the totals.
3. **The total is transparency, not an oracle.** A spread under ~2 weighted points
   is noise for a one-way door — fall back to reasoning about the dominant
   attributes (the highest-weight columns and the tradeoff points from Step 4),
   not the arithmetic.
4. If two options tie, the **more reversible** one wins the tie by default — the
   asymmetry of regret favors the cheaper mistake.

## ATAM-style sensitivity (one-way doors)

- **Sensitivity point** — an architectural decision that strongly affects *one*
  attribute. Name them; they are where the leverage is.
- **Tradeoff point** — a decision that affects *multiple* attributes in opposite
  directions (improves one, degrades another). These are the genuine costs;
  surface every one.
- **Risk** — a decision whose consequences are uncertain. Flag for a spike or a
  fitness function rather than guessing a score.

## Anti-patterns

- Scoring against 12 attributes — dilutes signal; cap at ~7.
- Identical scores down a column — either the attribute doesn't discriminate
  (drop it) or you're not thinking hard enough (the option *does* differ).
- Letting the weighted total override a clear dominant-attribute argument.
- Confusing a hard constraint ("must run on-prem") with a scored attribute — a
  constraint *eliminates*, it is not a column.
