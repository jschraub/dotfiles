#!/usr/bin/env bash
# Clone-or-update only Matt Pocock's productivity and engineering skills globally.
# OpenCode discovers SKILL.md recursively inside this sparse checkout.
#
# Usage: ./setup.sh mattpocock-skills (or run this script directly).
# Override the source/location with MATTPOCOCK_SKILLS_REPO / MATTPOCOCK_SKILLS_DIR.
# Re-runs fast-forward to the latest upstream version; dirty checkouts are left alone.

set -euo pipefail

REPO_URL="${MATTPOCOCK_SKILLS_REPO:-https://github.com/mattpocock/skills.git}"
SKILLS_DIR="${MATTPOCOCK_SKILLS_DIR:-$HOME/.config/opencode/skills/mattpocock-skills}"
CATEGORIES=(skills/productivity skills/engineering)

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || error "git is required"

if [[ -d "$SKILLS_DIR/.git" ]]; then
    info "existing checkout at $SKILLS_DIR"
    if [[ -n "$(git -C "$SKILLS_DIR" status --porcelain)" ]]; then
        warn "checkout has uncommitted changes - not pulling"
    else
        git -C "$SKILLS_DIR" sparse-checkout set --cone "${CATEGORIES[@]}"
        if ! git -C "$SKILLS_DIR" pull --ff-only --quiet; then
            warn "could not fast-forward (network error or diverged branch?) - leaving as-is"
        else
            ok "updated to $(git -C "$SKILLS_DIR" rev-parse --short HEAD)"
        fi
    fi
elif [[ -e "$SKILLS_DIR" || -L "$SKILLS_DIR" ]]; then
    error "$SKILLS_DIR exists but is not a git checkout - move it aside first"
else
    info "cloning productivity + engineering skills from $REPO_URL -> $SKILLS_DIR"
    mkdir -p "$(dirname "$SKILLS_DIR")"
    git clone --quiet --sparse "$REPO_URL" "$SKILLS_DIR"
    git -C "$SKILLS_DIR" sparse-checkout set --cone "${CATEGORIES[@]}"
    ok "cloned $(git -C "$SKILLS_DIR" rev-parse --short HEAD)"
fi

for category in "${CATEGORIES[@]}"; do
    [[ -d "$SKILLS_DIR/$category" ]] || error "$category directory missing from $SKILLS_DIR"
done
warn "Quit and restart OpenCode for Matt Pocock's productivity and engineering skills to load."
