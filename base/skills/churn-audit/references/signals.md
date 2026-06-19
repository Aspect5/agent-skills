# Churn signals — how to compute and read them

Load only when interpreting `churn_report.py` output. These signals turn raw git
history into architectural evidence. None is a verdict; each is a prompt.

## Why relative churn, not absolute (Nagappan & Ball, ICSE'05)

Absolute churn (total added+deleted lines) over-ranks large files: a 4,000-line
service that grew by 400 lines looks "hotter" than a 60-line module rewritten
three times, even though the small module is the one that is genuinely unstable.
**Relative churn normalizes by size**, so instability — not size — drives the
ranking. The script computes four relative measures inspired by that work:

| Field | Formula | Read it as |
|---|---|---|
| `relative_churn` (M1) | churned LOC / current LOC | >1 ⇒ the file was rewritten more than its own size in the window — high instability. <0.2 ⇒ touched lightly. |
| `active_weeks` (M5 input) | distinct ISO weeks with a change | Many weeks ⇒ sustained churn (drip), not one big drop. One week + high churn ⇒ a single migration. |
| `churn_ratio` (M7) | (additions+1)/(deletions+1) | ≈1 ⇒ rewrite-in-place / thrash (delete-and-replace). ≫1 ⇒ growth. ≪1 ⇒ shrinking/being-deleted. |
| `recency_weight` | linear in age, [0.5, 1.0] | Recent churn weighted higher; old, settled churn is discounted. |

## Hotspot score (the ranking key)

```
hotspot_score = recency_weight × relative_churn × log1p(complexity)
```

The multiplication is deliberate: **churn and complexity are only dangerous
together.**

- High churn on a *simple* file (`complexity` small) is cheap to keep changing —
  low score, leave it.
- High churn on a *complex* file is the expensive, decaying hotspot — high score,
  investigate first.
- `log1p` damps complexity so a single 5,000-line file cannot swamp the list; it
  rewards genuinely complex *and* unstable code.

`complexity` here is a **proxy**: source LOC + a bounded nesting-depth bonus,
language-agnostic and cheap. It is intentionally not cyclomatic complexity.
**Escalate to a real cyclomatic/cognitive-complexity tool for the top-K hotspots
only** (e.g. `radon cc`, `lizard`, `gocyclo`), where the extra precision pays off.

### Complexity trend (read the direction)

A static complexity number is less informative than its trajectory across the
window. Spot-check with `git log -p -- <path>` or by re-running the report on an
earlier sub-window:

- **Rising** complexity + high churn ⇒ the area is *decaying* — each change makes
  the next harder. Prime refactor candidate.
- **Falling** complexity + high churn ⇒ the area is *healing* (an in-progress
  cleanup). Often "leave alone — let the refactor finish".

## Change coupling (degree)

Two files are *coupled* when they tend to change in the same commit.

```
degree = co_changes / min(commits_touching_a, commits_touching_b)
```

- Uses `min` (not the larger denominator) so a strong asymmetric dependency still
  stands out: if B almost never changes without A, that's coupling even if A
  changes often alone.
- `--coupling-min-commits` (default 3) drops low-N noise — two files that
  co-changed once are not "coupled".
- **Only cross-boundary coupling is reported by default.** A file and its own unit
  test co-changing (`foo.py` ↔ `test_foo.py`) is expected and healthy. Coupling
  that **crosses a module/architectural boundary** (`api/handler.py` ↔
  `services/other_domain/state.py`) is the smell: a leaky abstraction, a duplicated
  source of truth, or a contract whose two sides aren't isolated. Boundaries are
  inferred from path depth (`--boundary-depth`, default 2) and overridable with
  `--boundary <prefix>` / a profile `boundaries` list / `CHURN_BOUNDARIES`.
- **Source ↔ own-test pairs are never reported as crossing**, even when tests live
  in a sibling tree the prefix-boundary heuristic would split (`src/` + `tests/`,
  `src/main` + `src/test`, `pkg/foo.go` + `pkg/foo_test.go`). The script matches the
  test↔source *naming* relationship (`test_x`/`x_test`/`x.test`/`x.spec`/`XTest`/
  `XSpec` ↔ `x`) and treats such a pair as intra-boundary regardless of directory.
  This match is **exact-stem and deliberately conservative**: a test whose name does
  not share the source stem (e.g. `schemas.py` ↔ `test_artifact_schemas.py`, or a
  prefix-stripped `check_x.py` ↔ `test_x.py`) is *not* auto-suppressed — it surfaces
  in the table, and **you demote it by judgment** if on inspection it is genuinely
  just that file's test. Conservative on purpose: aggressive fuzzy matching would
  hide real cross-module coupling (a worse failure for an advisory than a residual
  test pair you eyeball away).

A high-degree cross-boundary pair is the strongest single architectural signal in
the report — chase it in Step 3.

## Ownership / bus-factor (org metrics out-predict code metrics)

Empirically (Nagappan et al., organizational-structure studies), *who* changes a
file predicts defects better than *how* the code looks. The script reports:

| Field | Meaning | Risk read |
|---|---|---|
| `authors` | distinct authors in the window | 1 ⇒ knowledge silo; very high ⇒ no clear owner ("everybody's, nobody's"). |
| `bus_factor` | smallest set of top authors covering 50% of the file's commits | 1 ⇒ a single person holds the knowledge — fragile to departure. |
| `minor_author_fraction` | share of authors who each made <20% of the file's commits | High ⇒ many drive-by edits; correlates with diffuse ownership and higher defect risk. |

A hotspot with `bus_factor: 1` **and** high `minor_author_fraction` is an
*organizational* hotspot even if the code reads cleanly: one owner, many tourists.
The fix may be ownership/docs, not a refactor.

## Filtering noise (so the ranking is trustworthy)

- **Excluded by default**: generated code, lockfiles, vendored/`node_modules`/`vendor`,
  build output, snapshots, and migrations. Add project-specific generated paths with
  `--exclude '<regex>'`.
- **Bulk commits** (a mass-format or mass-rename touching > `--bulk-threshold`
  files, default 50) are dropped from coupling automatically (they would couple
  everything to everything) and listed in the report's Notes. Add
  `--drop-bulk-from-churn` to also remove them from per-file churn when a single
  reformat is distorting the ranking.
- **Renames** are followed: `git`'s `a => b` and `src/{x => y}/f` tokens resolve to
  the destination path so a renamed file's history isn't split.
