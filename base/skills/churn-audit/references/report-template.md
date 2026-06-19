# Advisory report template

Load when writing the deliverable (Workflow Step 6). Write the FULL report to a
file (default `churn-advisory.md` at the repo root, or a profile/user-named path),
**incrementally** — do not buffer the whole thing in context. Then emit only a
5-8 line summary inline (top 3 hotspots + the single best first move + the file
path).

Lead with the advisory, then the evidence. Keep it tied to evidence — every claim
references a `file` + a signal (commits, relative_churn, a coupling pair, or a PR).

```markdown
# Churn-Driven Architecture Advisory

_Window: <since/range> - generated <date> - advisory only (no code changed)._

## Executive Read
- The dominant hotspot is `<path>` - <one-line why it keeps changing>.
- Overall this looks <healthy | mixed | unhealthy> because <evidence>.
- The single best first move is <smallest high-payoff step>.

## Hotspot Table
| # | Area | Hotspot | RelChurn | Commits | Cx | BusFactor | Read | Recommendation |
|--:|---|--:|--:|--:|--:|--:|---|---|
| 1 | `path` | 41.8 | 15.5 | 3 | 22 | 1 | duplicate source of truth | extract single owner |
<!-- rank by hotspot_score; copy the numbers straight from churn_report.py -->

## Cross-boundary Coupling
| A | B | Co-changes | Degree | Crosses boundary | Architectural read |
|---|---|--:|--:|:--:|---|
<!-- only boundary-crossing pairs; intra-boundary (file+its test) is expected -->

## Deep Dives
### Area: `path/to/hot/file`
- **Evidence:** commits=<n>, relative_churn=<x>, complexity=<c>, bus_factor=<b>,
  coupled with `<other>` (degree <d>); PRs <#...> show <pattern>.
- **Current shape:** <responsibilities + dependencies>.
- **Failure mode:** <checklist base:id> - why each change is expensive/risky.
- **If starting over:** <cleaner boundary or flow>.
- **Recommendation:** first safe step -> follow-up -> how to verify. Name the
  payoff, the risk, and the migration path.

## Leave Alone
- `<path>` - high churn but explained by <active feature work | planned migration |
  generated code | in-progress healing refactor>. No action.

## Action Plan (ranked by future-change cost removed, not raw churn)
1. <lowest-risk advisory/doc/ownership step>.
2. <medium refactor - with its safety net and verification>.
3. <larger architectural move - with explicit preconditions and a back-out path>.
```

## Inline summary shape (what the user sees in the chat)

Keep it to ~5-8 lines:

```
Churn audit (90d) -> churn-advisory.md
Top hotspots: 1) services/foo.py (rewritten 15x its size, bus_factor 1)
              2) intake_service.py (god file, 40 commits, rising complexity)
              3) sandbox.py (complex + coupled across the api boundary)
Best first move: extract the duplicated <X> contract out of foo.py / bar.py.
Leave alone: migrations/* (expected churn). Full report + action plan in the file.
```
