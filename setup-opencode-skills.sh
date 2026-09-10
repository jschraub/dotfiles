#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_PACKAGE="opencode-skills"
TARGET_DIR="$HOME/.config/opencode"

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*" >&2; exit 1; }

command -v stow >/dev/null 2>&1 || error "GNU Stow is required"
[[ -d "$SCRIPT_DIR/$SKILLS_PACKAGE/skills" ]] || error "skills not found in $SCRIPT_DIR/$SKILLS_PACKAGE"

mkdir -p "$TARGET_DIR"
info "Stowing OpenCode skills into $TARGET_DIR/skills..."
stow -R --no-folding -t "$TARGET_DIR" -d "$SCRIPT_DIR" "$SKILLS_PACKAGE"
warn "Quit and restart OpenCode for the skills to load."
