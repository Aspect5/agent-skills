#!/usr/bin/env python3
"""OPTIONAL example helper — delete it if your skill needs no deterministic script.

Shows the script contract every skill script must follow: stdlib-only, self-roots via
`git rev-parse --show-toplevel` (so it works from any subdirectory), accepts --json,
and exits non-zero on a hard failure. Invoke as: python3 "<path-to-skill>/scripts/example.py" --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def git_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return Path(out) if out else None


def main() -> None:
    ap = argparse.ArgumentParser(description="Example skill helper.")
    ap.add_argument("--repo", default=".", help="Path inside the target repo (default: cwd)")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    args = ap.parse_args()

    root = git_root(Path(args.repo).resolve())
    if root is None:
        msg = "not a git repository (or git not installed)"
        sys.stdout.write(json.dumps({"ok": False, "error": msg}) + "\n") if args.json else sys.stderr.write(f"error: {msg}\n")
        sys.exit(1)

    result = {"ok": True, "repo_root": str(root)}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"repo_root: {root}")


if __name__ == "__main__":
    main()
