#!/usr/bin/env bash
#
# install-matrix.sh — fetch and install fw16-ledmatrix.
#
# The LED Matrix status daemon lives in its own repo rather than in this one:
# it is a standalone project that should be installable by people who are not
# me, so dotfiles only knows how to fetch it and invoke its own installer.
#
# Clone-or-pull into $MATRIX_DIR (default ~/code/matrix), then delegate to that
# repo's install.sh, which owns the udev rule and anything else host-side.
#
# Safe to re-run. A dirty or diverged checkout is left alone with a warning
# rather than clobbered — this is a working directory, not a deployment target.
#
# Usage:
#   ./install-matrix.sh
#   MATRIX_DIR=/somewhere/else ./install-matrix.sh

set -euo pipefail

REPO_URL="${MATRIX_REPO:-https://github.com/jschraub/fw16-ledmatrix.git}"
MATRIX_DIR="${MATRIX_DIR:-$HOME/code/matrix}"

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || error "git is required"

if [[ -d "$MATRIX_DIR/.git" ]]; then
    info "existing checkout at $MATRIX_DIR"
    if [[ -n "$(git -C "$MATRIX_DIR" status --porcelain)" ]]; then
        warn "checkout has uncommitted changes — not pulling"
    elif ! git -C "$MATRIX_DIR" pull --ff-only --quiet; then
        warn "could not fast-forward (diverged branch?) — leaving as-is"
    else
        ok "updated to $(git -C "$MATRIX_DIR" rev-parse --short HEAD)"
    fi
elif [[ -e "$MATRIX_DIR" ]]; then
    error "$MATRIX_DIR exists but is not a git checkout — move it aside first"
else
    info "cloning $REPO_URL -> $MATRIX_DIR"
    mkdir -p "$(dirname "$MATRIX_DIR")"
    git clone --quiet "$REPO_URL" "$MATRIX_DIR"
    ok "cloned $(git -C "$MATRIX_DIR" rev-parse --short HEAD)"
fi

[[ -x "$MATRIX_DIR/install.sh" ]] || error "$MATRIX_DIR/install.sh missing or not executable"

info "running $MATRIX_DIR/install.sh"
"$MATRIX_DIR/install.sh"
