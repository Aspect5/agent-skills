#!/usr/bin/env python3
"""Churn-driven architecture signal report.

Computes hotspots from git history using *relative* churn (Nagappan & Ball,
ICSE'05) rather than raw line counts, multiplies churn by a complexity proxy to
rank true hotspots, surfaces cross-boundary change coupling, and attaches
ownership / bus-factor signals. Dependency-light: Python stdlib + git only.

The script self-roots via `git rev-parse --show-toplevel`, so it works from any
working directory inside a repo (or pass --repo). It supports --json for machine
consumption and exits non-zero with an explicit message on failure.

Signals, with their lineage:
  relative_churn   M1  churned LOC / current LOC            (a tiny file rewritten
                                                             often outranks a huge
                                                             file with equal absolute
                                                             churn)
  commits          how many distinct commits touched the file in the window
  age_weeks        M5  weeks-with-a-change / file lifetime, recency-weighted
  churn_ratio      M7  added / deleted ratio (≈1 => rewrite-in-place / thrash;
                                              >>1 => growth; <<1 => shrinking)
  complexity       LOC + nesting proxy (cheap, language-agnostic). Cyclomatic is
                   intentionally NOT computed here — escalate to it by hand for the
                   top-K only, per the skill workflow.
  hotspot_score    recency_weight * relative_churn * log1p(complexity).
                   High churn on a SIMPLE file is cheap to fix; high churn on a
                   COMPLEX file is the expensive, decaying hotspot.
  authors          distinct authors; minor_fraction = authors who made <20% of the
                   file's commits; bus_factor = authors covering >=50% of commits.
                   (Org metrics out-predict code metrics — Nagappan et al.)
  coupling         pairs that co-change at least --coupling-min-commits times
                   with a co-change degree >= --coupling-min-degree, flagged
                   only when the pair crosses a module boundary (a source file
                   and its own unit test never count as crossing).

Nothing here is a verdict. Churn is a prompt for investigation; the LLM workflow
turns these numbers into architectural advice.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

# --- tunables (documented, not voodoo) -------------------------------------

# Paths excluded from hotspot ranking: generated, vendored, lockfiles, build
# artifacts, snapshots, migrations. Churn here is expected and not architectural.
DEFAULT_EXCLUDE_PATTERNS = (
    r"(^|/)(node_modules|vendor|third_party|dist|build|out|target|\.next|\.venv|__pycache__)/",
    r"(^|/)(migrations?|alembic)/",  # one-way, append-only churn by design
    r"(^|/)__snapshots__/",
    r"\.(lock|min\.js|min\.css|map|generated\.[a-z]+)$",
    r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Cargo\.lock|go\.sum|composer\.lock|Gemfile\.lock)$",
    r"(^|/)(\.gitignore|\.gitattributes)$",
)

# Author share below this fraction of a file's commits => "minor contributor".
MINOR_AUTHOR_FRACTION = 0.20
# Authors needed to cumulatively cover this share of commits => bus factor.
BUS_FACTOR_COVERAGE = 0.50
# A mass-format / mass-rename commit touching more files than this is dropped
# from coupling (it would couple everything to everything) but still counts
# toward per-file churn unless --drop-bulk-from-churn is set.
DEFAULT_BULK_COMMIT_FILE_THRESHOLD = 50

# Nesting characters used as a language-agnostic complexity proxy.
_OPEN_BRACES = "{(["


class ChurnError(RuntimeError):
    """A fatal, explained error (printed to stderr; non-zero exit)."""


@dataclass
class FileChurn:
    path: str
    commits: set[str] = field(default_factory=set)
    additions: int = 0
    deletions: int = 0
    last_date: str = ""
    last_commit: str = ""
    last_subject: str = ""
    # author login/name -> number of this file's commits they authored
    author_commits: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    # distinct YYYY-WW week buckets in which this file changed
    active_weeks: set[str] = field(default_factory=set)

    @property
    def churned_lines(self) -> int:
        return self.additions + self.deletions

    @property
    def churn_ratio(self) -> float:
        # added/deleted; +1 smoothing so a pure-add file is finite, not inf.
        return round((self.additions + 1) / (self.deletions + 1), 2)


def run_git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:  # git not installed
        raise ChurnError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        msg = (exc.stderr or "").strip() or f"git {' '.join(args)} failed"
        raise ChurnError(msg) from exc
    return result.stdout


def resolve_repo_root(repo_arg: str | None) -> Path:
    """Self-root: prefer an explicit --repo, else the enclosing git toplevel."""
    start = Path(repo_arg).resolve() if repo_arg else Path.cwd()
    if not start.exists():
        raise ChurnError(f"--repo path does not exist: {start}")
    try:
        top = run_git(["rev-parse", "--show-toplevel"], start).strip()
    except ChurnError as exc:
        raise ChurnError(
            f"not inside a git repository (looked from {start}): {exc}"
        ) from exc
    return Path(top)


def compile_excludes(extra: list[str] | None) -> list[re.Pattern[str]]:
    patterns = list(DEFAULT_EXCLUDE_PATTERNS) + list(extra or [])
    compiled = []
    for pat in patterns:
        try:
            compiled.append(re.compile(pat))
        except re.error as exc:
            raise ChurnError(f"bad exclude regex {pat!r}: {exc}") from exc
    return compiled


def is_excluded(path: str, excludes: list[re.Pattern[str]]) -> bool:
    return any(rx.search(path) for rx in excludes)


def parse_log(
    cwd: Path,
    since: str,
    base_range: str | None,
    max_commits: int | None,
    excludes: list[re.Pattern[str]],
    bulk_threshold: int,
    drop_bulk_from_churn: bool,
) -> tuple[dict[str, FileChurn], list[tuple[str, list[str]]], list[str]]:
    """Parse `git log --numstat`.

    Returns (per-file churn, [(commit, [files])] for coupling, [warnings]).
    """
    # %x09 = tab; sentinel line keeps commit metadata unambiguous vs numstat.
    pretty = "--C--%H%x09%ad%x09%an%x09%s"
    args = ["log", "--no-merges", "--date=short", f"--pretty=format:{pretty}", "--numstat"]
    if base_range:
        args.append(base_range)
    else:
        args.append(f"--since={since}")
    if max_commits:
        args.insert(1, f"-n{max_commits}")

    files: dict[str, FileChurn] = {}
    commit_files: list[tuple[str, list[str]]] = []
    warnings: list[str] = []

    cur_commit = cur_date = cur_author = cur_subject = ""
    pending: list[str] = []

    def flush_commit() -> None:
        if not cur_commit:
            return
        # Bulk commit handling for coupling (always) and churn (optional).
        if len(pending) > bulk_threshold:
            warnings.append(
                f"commit {cur_commit[:8]} touched {len(pending)} files "
                f"(> {bulk_threshold}); excluded from coupling"
                + ("; excluded from churn" if drop_bulk_from_churn else "")
            )
            if drop_bulk_from_churn:
                # roll back the per-file contributions we just recorded
                for p in pending:
                    fc = files.get(p)
                    if fc and cur_commit in fc.commits:
                        fc.commits.discard(cur_commit)
                        fc.author_commits[cur_author] -= 1
                        if fc.author_commits[cur_author] <= 0:
                            fc.author_commits.pop(cur_author, None)
            return  # not added to coupling
        if len(pending) >= 2:
            commit_files.append((cur_commit, list(pending)))

    out = run_git(args, cwd)
    for line in out.splitlines():
        if not line:
            continue
        if line.startswith("--C--"):
            flush_commit()
            pending = []
            parts = line[len("--C--"):].split("\t", 3)
            cur_commit = parts[0]
            cur_date = parts[1] if len(parts) > 1 else ""
            cur_author = parts[2] if len(parts) > 2 else "unknown"
            cur_subject = parts[3] if len(parts) > 3 else ""
            continue

        cols = line.split("\t")
        if len(cols) != 3:
            continue
        raw_add, raw_del, path = cols
        if raw_add == "-" or raw_del == "-":  # binary
            continue
        # `git log` renders renames as "old => new" or "a/{b => c}/d" — take the
        # destination path so churn follows the file across renames.
        if "=>" in path:
            path = _resolve_rename(path)
        if is_excluded(path, excludes):
            continue

        fc = files.setdefault(path, FileChurn(path=path))
        fc.commits.add(cur_commit)
        fc.additions += int(raw_add)
        fc.deletions += int(raw_del)
        fc.author_commits[cur_author] += 1
        if cur_date:
            fc.active_weeks.add(_week_bucket(cur_date))
        if not fc.last_date or cur_date >= fc.last_date:
            fc.last_date = cur_date
            fc.last_commit = cur_commit
            fc.last_subject = cur_subject
        pending.append(path)

    flush_commit()
    return files, commit_files, warnings


def _resolve_rename(path: str) -> str:
    """Turn a git rename token into the destination path.

    Handles both "old => new" and the brace form "src/{a => b}/file".
    """
    brace = re.search(r"\{(.*?) => (.*?)\}", path)
    if brace:
        return path[: brace.start()] + brace.group(2) + path[brace.end():]
    if " => " in path:
        return path.split(" => ", 1)[1]
    return path


def _week_bucket(date_str: str) -> str:
    # date_str is YYYY-MM-DD from --date=short
    try:
        import datetime as _dt

        d = _dt.date.fromisoformat(date_str)
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    except Exception:
        return date_str  # degrade gracefully; never crash on a weird date


# --- complexity proxy -------------------------------------------------------


def complexity_proxy(repo: Path, rel_path: str) -> int:
    """Cheap, language-agnostic complexity: source LOC + nesting depth bonus.

    Reads the CURRENT file. A missing/deleted file => 0 (it no longer costs us).
    This is a proxy on purpose; escalate to real cyclomatic complexity by hand
    for the top-K hotspots only.
    """
    fpath = repo / rel_path
    try:
        text = fpath.read_text(encoding="utf-8", errors="ignore")
    except (OSError, ValueError):
        return 0
    loc = 0
    max_depth = 0
    depth = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # skip the most common single-line comment forms
        if stripped.startswith(("#", "//", "*", "/*", "<!--")):
            continue
        loc += 1
        for ch in line:
            if ch in _OPEN_BRACES:
                depth += 1
                max_depth = max(max_depth, depth)
            elif ch in ")]}":
                depth = max(0, depth - 1)
    # nesting amplifies; clamp the bonus so a deeply-bracketed one-liner
    # cannot dominate genuine size.
    return loc + min(max_depth, 12) * 5


def current_loc(repo: Path, rel_path: str) -> int:
    fpath = repo / rel_path
    try:
        text = fpath.read_text(encoding="utf-8", errors="ignore")
    except (OSError, ValueError):
        return 0
    return sum(1 for ln in text.splitlines() if ln.strip())


# --- scoring ----------------------------------------------------------------


def recency_weight(last_date: str, window_days: int) -> float:
    """Linear recency weight in [0.5, 1.0]; recent churn weighted higher."""
    try:
        import datetime as _dt

        last = _dt.date.fromisoformat(last_date)
        age = (_dt.date.today() - last).days
    except Exception:
        return 0.75
    if window_days <= 0:
        return 1.0
    frac = max(0.0, min(1.0, 1.0 - age / window_days))
    return round(0.5 + 0.5 * frac, 3)


def score_files(
    repo: Path,
    files: dict[str, FileChurn],
    window_days: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for fc in files.values():
        cloc = current_loc(repo, fc.path)
        # relative churn (M1): churned lines vs current size. Files deleted in
        # the window have cloc==0; fall back to churned_lines as the denominator
        # floor so they are not div-by-zero or infinite.
        denom = cloc if cloc > 0 else max(fc.churned_lines, 1)
        relative_churn = round(fc.churned_lines / denom, 3)
        cx = complexity_proxy(repo, fc.path)
        rweight = recency_weight(fc.last_date, window_days)
        # hotspot = recency * relative_churn * log1p(complexity).
        hotspot = round(rweight * relative_churn * math.log1p(cx), 4)

        authors = dict(fc.author_commits)
        total_author_commits = sum(authors.values()) or 1
        minor = [
            a
            for a, n in authors.items()
            if n / total_author_commits < MINOR_AUTHOR_FRACTION
        ]
        # bus factor: smallest set of top authors covering BUS_FACTOR_COVERAGE.
        bus = 0
        acc = 0
        for _, n in sorted(authors.items(), key=lambda kv: kv[1], reverse=True):
            acc += n
            bus += 1
            if acc / total_author_commits >= BUS_FACTOR_COVERAGE:
                break

        rows.append(
            {
                "path": fc.path,
                "commits": len(fc.commits),
                "churned_lines": fc.churned_lines,
                "additions": fc.additions,
                "deletions": fc.deletions,
                "current_loc": cloc,
                "relative_churn": relative_churn,
                "churn_ratio": fc.churn_ratio,
                "complexity": cx,
                "active_weeks": len(fc.active_weeks),
                "recency_weight": rweight,
                "hotspot_score": hotspot,
                "authors": len(authors),
                "minor_author_fraction": round(len(minor) / max(len(authors), 1), 2),
                "bus_factor": bus,
                "last_date": fc.last_date,
                "last_commit": fc.last_commit[:8],
                "last_subject": fc.last_subject,
            }
        )
    rows.sort(key=lambda r: (r["hotspot_score"], r["commits"]), reverse=True)
    return rows


# --- coupling ---------------------------------------------------------------


def infer_boundary(path: str, boundary_depth: int, overrides: list[str]) -> str:
    """Map a file to its module/architectural boundary.

    Override with --boundary (repeatable, prefix match). Otherwise use the
    path prefix at boundary_depth.
    """
    for ov in overrides:
        if path.startswith(ov.rstrip("/") + "/") or path == ov:
            return ov.rstrip("/")
    parts = Path(path).parts
    return "/".join(parts[:boundary_depth]) if len(parts) >= boundary_depth else parts[0]


# A source file and its own unit test co-changing is EXPECTED, not an
# architectural smell — the skill's signals.md promises this is filtered out.
# Directory-prefix boundaries do not catch it when tests live in a sibling tree
# (`src/` + `tests/`, `src/main` + `src/test`, `pkg/` + `pkg/..._test.go`), so
# match the test<->source naming relationship directly and treat such a pair as
# intra-boundary regardless of where the test file physically lives.
_TEST_STEM_RX = re.compile(
    r"""^(?:
            test_(?P<a>.+)        |   # python  test_foo
            (?P<b>.+)_test        |   # go/py   foo_test
            (?P<c>.+)\.test       |   # js/ts   foo.test
            (?P<d>.+)\.spec       |   # js/ts   foo.spec
            (?P<e>.+)Test         |   # java    FooTest
            (?P<f>.+)Spec             # jvm     FooSpec
        )$""",
    re.VERBOSE,
)


def _source_stem(path: str) -> str:
    """Return the source stem a test file pairs with, else the file's own stem.

    e.g. `backend/tests/test_foo.py` -> `foo`; `foo.test.ts` -> `foo`;
    a non-test file returns its plain stem (`bar.py` -> `bar`). Used only to
    recognise a source<->own-test pair so it is not mis-reported as a
    cross-boundary smell.
    """
    name = Path(path).name
    # strip a compound extension like `.test.ts` down to the first dot's stem
    stem = name.split(".", 1)[0] if "." in name else name
    # `foo.test.ts` / `foo.spec.tsx`: stem is `foo` only after we also peel the
    # `.test` / `.spec` marker that split() left attached to the extension.
    m = _TEST_STEM_RX.match(Path(name).stem)
    if m:
        for g in m.groupdict().values():
            if g:
                return g
    return stem


def _is_source_test_pair(a: str, b: str) -> bool:
    """True if (a, b) is a source file and its own unit test (either order)."""
    sa, sb = _source_stem(a), _source_stem(b)
    if not sa or sa != sb:
        return False
    # exactly one of the two must look like a test file; otherwise these are
    # two unrelated files that merely share a stem.
    return _looks_like_test(a) != _looks_like_test(b)


def _looks_like_test(path: str) -> bool:
    return bool(_TEST_STEM_RX.match(Path(path).stem))


def compute_coupling(
    commit_files: list[tuple[str, list[str]]],
    min_degree: float,
    min_pair_commits: int,
    boundary_depth: int,
    boundary_overrides: list[str],
    cross_boundary_only: bool,
    top: int,
) -> list[dict[str, object]]:
    file_commits: dict[str, int] = defaultdict(int)
    pair_commits: dict[tuple[str, str], int] = defaultdict(int)
    for _commit, paths in commit_files:
        uniq = sorted(set(paths))
        for p in uniq:
            file_commits[p] += 1
        for a, b in combinations(uniq, 2):
            pair_commits[(a, b)] += 1

    rows: list[dict[str, object]] = []
    for (a, b), co in pair_commits.items():
        if co < min_pair_commits:
            continue
        # degree = co-changes / changes of the LESS-changed file (asymmetric
        # coupling is real; using min makes a strong pair stand out).
        base = min(file_commits[a], file_commits[b]) or 1
        degree = co / base
        if degree < min_degree:
            continue
        ba = infer_boundary(a, boundary_depth, boundary_overrides)
        bb = infer_boundary(b, boundary_depth, boundary_overrides)
        # A source file and its own unit test is expected co-change, never a
        # cross-boundary smell — even when tests live in a sibling directory
        # tree that the prefix-boundary heuristic would otherwise split.
        crosses = ba != bb and not _is_source_test_pair(a, b)
        if cross_boundary_only and not crosses:
            continue
        rows.append(
            {
                "a": a,
                "b": b,
                "co_changes": co,
                "degree": round(degree, 2),
                "boundary_a": ba,
                "boundary_b": bb,
                "crosses_boundary": crosses,
            }
        )
    # cross-boundary pairs first (they are the architectural smell), then degree.
    rows.sort(key=lambda r: (r["crosses_boundary"], r["degree"], r["co_changes"]), reverse=True)
    return rows[:top]


# --- output -----------------------------------------------------------------


def print_markdown(
    rows: list[dict[str, object]],
    coupling: list[dict[str, object]],
    warnings: list[str],
    window_label: str,
    top: int,
) -> None:
    print("# Churn Signal Report")
    print()
    print(f"Window: {window_label}. Ranked by hotspot_score "
          "(recency × relative_churn × log1p(complexity)).")
    print()
    print("## Hotspots")
    print()
    print("| # | File | Hotspot | RelChurn | Commits | Cx | Authors | BusFactor | Last |")
    print("|--:|---|--:|--:|--:|--:|--:|--:|---|")
    for i, r in enumerate(rows[:top], 1):
        print(
            f"| {i} | `{r['path']}` | {r['hotspot_score']} | {r['relative_churn']} | "
            f"{r['commits']} | {r['complexity']} | {r['authors']} | {r['bus_factor']} | "
            f"{r['last_date']} `{r['last_commit']}` |"
        )
    print()
    print("Legend: Hotspot=composite; RelChurn=churned/current LOC (>1 = rewritten "
          "more than its size); Cx=complexity proxy (LOC+nesting); BusFactor=authors "
          "covering 50% of commits (1 = knowledge silo).")
    print()
    print("## Cross-boundary change coupling")
    print()
    if not coupling:
        print("_No coupling pairs above the threshold._")
    else:
        print("| A | B | Co-changes | Degree | Crosses boundary |")
        print("|---|---|--:|--:|:--:|")
        for r in coupling:
            mark = "⚠️ yes" if r["crosses_boundary"] else "no"
            print(
                f"| `{r['a']}` | `{r['b']}` | {r['co_changes']} | {r['degree']} | {mark} |"
            )
    if warnings:
        print()
        print("## Notes")
        for w in warnings:
            print(f"- {w}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Churn-driven architecture signal report (relative churn + coupling + ownership)."
    )
    parser.add_argument("--repo", default=None, help="Repo dir (default: enclosing git toplevel)")
    parser.add_argument("--since", default="90 days ago", help="git --since value")
    parser.add_argument("--base-range", default=None,
                        help="Use a revision range instead of --since, e.g. 'origin/main..HEAD'")
    parser.add_argument("--window-days", type=int, default=90,
                        help="Window length in days for recency weighting (match --since)")
    parser.add_argument("--max-commits", type=int, default=None, help="Cap commits scanned")
    parser.add_argument("--top", type=int, default=30, help="Rows to print")
    parser.add_argument("--exclude", action="append", default=[],
                        help="Extra path-exclude regex (repeatable)")
    parser.add_argument("--boundary", action="append", default=[],
                        help="Boundary prefix override for coupling (repeatable)")
    parser.add_argument("--boundary-depth", type=int, default=2,
                        help="Path depth used to infer a module boundary")
    parser.add_argument("--coupling-min-degree", type=float, default=0.5,
                        help="Min co-change degree to report a coupling pair")
    parser.add_argument("--coupling-min-commits", type=int, default=3,
                        help="Min co-change count (drops low-N noise)")
    parser.add_argument("--all-coupling", action="store_true",
                        help="Report intra-boundary coupling too (default: cross-boundary only)")
    parser.add_argument("--bulk-threshold", type=int, default=DEFAULT_BULK_COMMIT_FILE_THRESHOLD,
                        help="Commits touching more files than this are dropped from coupling")
    parser.add_argument("--drop-bulk-from-churn", action="store_true",
                        help="Also exclude bulk commits from per-file churn")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown")
    args = parser.parse_args(argv)

    try:
        repo = resolve_repo_root(args.repo)
        excludes = compile_excludes(args.exclude)
        files, commit_files, warnings = parse_log(
            repo,
            args.since,
            args.base_range,
            args.max_commits,
            excludes,
            args.bulk_threshold,
            args.drop_bulk_from_churn,
        )
        if not files:
            raise ChurnError(
                "no churn found in window — widen --since or check the repo has history"
            )
        rows = score_files(repo, files, args.window_days)
        coupling = compute_coupling(
            commit_files,
            args.coupling_min_degree,
            args.coupling_min_commits,
            args.boundary_depth,
            args.boundary,
            cross_boundary_only=not args.all_coupling,
            top=min(args.top, 25),
        )
    except ChurnError as exc:
        print(f"churn_report: {exc}", file=sys.stderr)
        return 2

    window_label = args.base_range or args.since
    if args.json:
        print(json.dumps(
            {
                "repo": str(repo),
                "window": window_label,
                "window_days": args.window_days,
                "hotspots": rows[: args.top],
                "coupling": coupling,
                "warnings": warnings,
            },
            indent=2,
        ))
        return 0

    print_markdown(rows, coupling, warnings, window_label, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
