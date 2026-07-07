#!/usr/bin/env bash
# Replicate the base skills into a coding agent's skills directory.
# Idempotent, and COLLISION-SAFE: an existing skill of the same name that isn't
# ours is never deleted — it is reported and skipped (use --force to override).
#
#   (default)      target $CODEX_HOME/skills   (Codex,       default ~/.codex/skills)
#   --claude       target $CLAUDE_HOME/skills  (Claude Code, default ~/.claude/skills)
#   --copy         materialize standalone COPIES instead of symlinks
#   --force        back up a conflicting real dir to .superseded/ (or drop a foreign
#                  symlink) and install over it — off by default so nothing is clobbered
#   --no-external  install only base/skills/*; skip approved external packs
#
# The SKILL.md format is shared, so the same base/skills/* run natively in both
# Codex and Claude Code. Approved third-party packs (vendor/<pack>/ +
# scripts/external_skills.py) are staged and installed alongside the base into the
# SAME selected target unless --no-external is given. Restart the agent afterward.
set -euo pipefail

MODE="symlink"; TARGET="codex"; FORCE=0; INCLUDE_EXTERNAL=1
for arg in "$@"; do
  case "$arg" in
    --copy)        MODE="copy" ;;
    --claude)      TARGET="claude" ;;
    --codex)       TARGET="codex" ;;
    --force)       FORCE=1 ;;
    --no-external) INCLUDE_EXTERNAL=0 ;;
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
EXTERNAL_STAGE="$SKILLS_REPO/.generated/external-skills"
EXTERNAL_STATE_FILE="$DEST/.managed-external-skills"

mkdir -p "$DEST"

installed=0; skipped=(); backed_up=0

# Collision-safe replicate of every immediate subdir of $1 into $DEST.
# Honors $MODE (symlink|copy) and $FORCE; accumulates installed/skipped/backed_up.
install_root() {
  local root="$1"
  [ -d "$root" ] || return 0
  local d name src target kind
  for d in "$root"/*/; do
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
}

# --- external pack lifecycle (only exercised when INCLUDE_EXTERNAL=1) ---

collect_root_names() {
  local root="$1"; local d
  [ -d "$root" ] || return 0
  for d in "$root"/*/; do
    [ -d "$d" ] || continue
    basename "$d"
  done
}

name_in_list() {
  local needle="$1"; shift; local item
  for item in "$@"; do
    [ "$item" = "$needle" ] && return 0
  done
  return 1
}

# Remove external skills WE previously installed that are no longer exported.
prune_managed_external_skills() {
  local current=("$@"); local name target
  [ -f "$EXTERNAL_STATE_FILE" ] || return 0
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    name_in_list "$name" "${current[@]+"${current[@]}"}" && continue
    target="$DEST/$name"
    if [ -L "$target" ]; then
      rm -f "$target"; echo "removed dropped external skill: $name"
    elif [ -e "$target" ]; then
      mkdir -p "$BACKUP_DIR"
      mv "$target" "$BACKUP_DIR/${name}-$(date +%Y%m%d-%H%M%S)"
      echo "backed up dropped external $name -> $BACKUP_DIR/"
    fi
  done < "$EXTERNAL_STATE_FILE"
}

write_managed_external_state() {
  local current=("$@")
  : > "$EXTERNAL_STATE_FILE"
  [ "${#current[@]}" -gt 0 ] && printf '%s\n' "${current[@]}" >> "$EXTERNAL_STATE_FILE"
  return 0
}

# --- install ---

before=$installed
install_root "$SKILLS_REPO/base/skills"
base_n=$((installed - before))

external_n=0
if [ "$INCLUDE_EXTERNAL" = "1" ] && [ -f "$SKILLS_REPO/scripts/external_skills.py" ]; then
  python3 "$SKILLS_REPO/scripts/external_skills.py" --repo-root "$SKILLS_REPO" export --output-dir "$EXTERNAL_STAGE"
  external_names=()
  while IFS= read -r _n; do [ -n "$_n" ] && external_names+=("$_n"); done \
    < <(collect_root_names "$EXTERNAL_STAGE")
  prune_managed_external_skills "${external_names[@]+"${external_names[@]}"}"
  before=$installed
  install_root "$EXTERNAL_STAGE"
  external_n=$((installed - before))
  write_managed_external_state "${external_names[@]+"${external_names[@]}"}"
fi

echo "Replicated $base_n base + $external_n external skill(s) into $DEST ($MODE mode, $AGENT)."
[ "$backed_up" -gt 0 ] && echo "Backed up $backed_up conflicting dir(s) to $BACKUP_DIR/."
if [ "${#skipped[@]}" -gt 0 ]; then
  echo "Skipped ${#skipped[@]} existing skill(s) — left untouched (use --force to override):"
  printf '  - %s\n' "${skipped[@]}"
fi
echo "RESTART $AGENT to pick up new skills."
