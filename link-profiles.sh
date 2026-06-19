#!/usr/bin/env bash
# Per-project: materialize an overlay's profiles into the project's .agents/profiles/
# so each base skill's context-absorption prelude finds them. Run from inside the project.
set -euo pipefail

proj="${1:?usage: link-profiles.sh <project-name>   (a dir under overlays/)}"
SKILLS_REPO="${SKILLS_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
src="$SKILLS_REPO/overlays/$proj/profiles"

[ -d "$src" ] || { echo "no overlay profiles at $src" >&2; exit 1; }

root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
dest="$root/.agents/profiles"
mkdir -p "$dest"

n=0
for p in "$src"/*.md; do
  [ -e "$p" ] || continue
  ln -sfn "$p" "$dest/$(basename "$p")"
  n=$((n+1))
done
echo "Linked $n profile(s) from overlays/$proj into $dest"
