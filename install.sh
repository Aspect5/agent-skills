#!/usr/bin/env bash
# Replicate the base skills into a coding agent's skills directory.
# Idempotent, and COLLISION-SAFE: an existing skill of the same name that isn't
# ours is never deleted — it is reported and skipped (use --force to override).
#
#   (default)    target $CODEX_HOME/skills   (Codex,       default ~/.codex/skills)
#   --claude     target $CLAUDE_HOME/skills  (Claude Code, default ~/.claude/skills)
#   --copy       materialize standalone COPIES instead of symlinks
#   --force      back up a conflicting real dir to .superseded/ (or drop a foreign
#                symlink) and install over it — off by default so nothing is clobbered
#
# The SKILL.md format is shared, so the same base/skills/* run natively in both
# Codex and Claude Code. Restart the agent afterward to pick up new skills.
set -euo pipefail

MODE="symlink"; TARGET="codex"; FORCE=0
for arg in "$@"; do
  case "$arg" in
    --copy)   MODE="copy" ;;
    --claude) TARGET="claude" ;;
    --codex)  TARGET="codex" ;;
    --force)  FORCE=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

SKILLS_REPO="${SKILLS_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
if [ "$TARGET" = "claude" ]; then
  DEST="${CLAUDE_HOME:-$HOME/.claude}/skills"; AGENT="Claude Code"
else
  DEST="${CODEX_HOME:-$HOME/.codex}/skills"; AGENT="Codex"
fi
BACKUP_DIR="$DEST/.superseded"

mkdir -p "$DEST"

installed=0; skipped=(); backed_up=0
for d in "$SKILLS_REPO"/base/skills/*/; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  src="${d%/}"
  target="$DEST/$name"

  # Already our symlink → idempotent skip.
  if [ -L "$target" ] && [ "$(readlink "$target")" = "$src" ]; then
    installed=$((installed+1)); continue
  fi
  # Copy mode already in place + identical → idempotent skip.
  if [ "$MODE" = "copy" ] && [ -d "$target" ] && [ ! -L "$target" ] \
     && diff -rq "$src" "$target" >/dev/null 2>&1; then
    installed=$((installed+1)); continue
  fi

  # Something else is in the way.
  if [ -e "$target" ] || [ -L "$target" ]; then
    if [ "$FORCE" -eq 1 ]; then
      if [ -L "$target" ]; then
        rm -f "$target"
      else
        mkdir -p "$BACKUP_DIR"
        mv "$target" "$BACKUP_DIR/${name}-$(date +%Y%m%d-%H%M%S)"
        backed_up=$((backed_up+1))
      fi
    else
      kind="dir"; [ -L "$target" ] && kind="symlink -> $(readlink "$target")"
      skipped+=("$name ($kind)")
      continue
    fi
  fi

  if [ "$MODE" = "copy" ]; then cp -R "$src" "$target"; else ln -s "$src" "$target"; fi
  installed=$((installed+1))
done

echo "Replicated $installed base skill(s) into $DEST ($MODE mode, $AGENT)."
[ "$backed_up" -gt 0 ] && echo "Backed up $backed_up conflicting dir(s) to $BACKUP_DIR/."
if [ "${#skipped[@]}" -gt 0 ]; then
  echo "Skipped ${#skipped[@]} existing skill(s) — left untouched (use --force to override):"
  printf '  - %s\n' "${skipped[@]}"
fi
echo "RESTART $AGENT to pick up new skills."
