#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE="$PROJECT_DIR/skills/freerouter"
SKILLS_ROOT="${CODEX_HOME:-$HOME/.codex}/skills"
TARGET="$SKILLS_ROOT/freerouter"

mkdir -p "$SKILLS_ROOT"
if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
  printf '%s\n' "Skill destination already exists: $TARGET"
  exit 1
fi

ln -s "$SOURCE" "$TARGET"
printf '%s\n' "Installed FreeRouter skill: $TARGET"
