#!/usr/bin/env bash
# Replicate the base skills into $CODEX_HOME/skills. Idempotent + safe to re-run.
# Default: symlink (one git pull updates every machine).
#   --copy : materialize standalone COPIES instead (survive the repo moving/being deleted).
# Existing real dirs of the same name are backed up, never deleted.
set -euo pipefail

MODE="symlink"
[ "${1:-}" = "--copy" ] && MODE="copy"

SKILLS_REPO="${SKILLS_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
CODEX_SKILLS="${CODEX_HOME:-$HOME/.codex}/skills"
BACKUP_DIR="$CODEX_SKILLS/.superseded"

mkdir -p "$CODEX_SKILLS"

count=0
for d in "$SKILLS_REPO"/base/skills/*/; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  target="$CODEX_SKILLS/$name"

  # Symlink mode: skip if already the correct link.
  if [ "$MODE" = "symlink" ] && [ -L "$target" ] && [ "$(readlink "$target")" = "${d%/}" ]; then
    count=$((count+1)); continue
  fi

  # Copy mode: skip if an identical copy is already in place (keeps re-runs
  # idempotent instead of re-archiving every skill into .superseded/).
  if [ "$MODE" = "copy" ] && [ -d "$target" ] && [ ! -L "$target" ] \
     && diff -rq "${d%/}" "$target" >/dev/null 2>&1; then
    count=$((count+1)); continue
  fi

  # Anything in the way gets backed up (real dir) or removed (stale symlink).
  if [ -e "$target" ] || [ -L "$target" ]; then
    if [ -L "$target" ]; then
      rm -f "$target"
    else
      mkdir -p "$BACKUP_DIR"
      mv "$target" "$BACKUP_DIR/${name}-$(date +%Y%m%d-%H%M%S)"
      echo "backed up existing $name -> $BACKUP_DIR/"
    fi
  fi

  if [ "$MODE" = "copy" ]; then
    cp -R "${d%/}" "$target"
  else
    ln -s "${d%/}" "$target"
  fi
  count=$((count+1))
done

echo "Replicated $count base skill(s) into $CODEX_SKILLS ($MODE mode)"
echo "RESTART Codex to pick up new skills."
