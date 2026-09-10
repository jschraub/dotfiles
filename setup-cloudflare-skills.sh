#!/usr/bin/env bash
# Clone-or-update Cloudflare's OpenCode-compatible skills next to the global config.

set -euo pipefail

REPO_URL="${CLOUDFLARE_SKILLS_REPO:-https://github.com/cloudflare/skills.git}"
SKILLS_DIR="${CLOUDFLARE_SKILLS_DIR:-$HOME/.config/opencode/skills/cloudflare-skills}"

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || error "git is required"

if [[ -d "$SKILLS_DIR/.git" ]]; then
    info "existing checkout at $SKILLS_DIR"
    if [[ -n "$(git -C "$SKILLS_DIR" status --porcelain)" ]]; then
        warn "checkout has uncommitted changes - not pulling"
    elif ! git -C "$SKILLS_DIR" pull --ff-only --quiet; then
        warn "could not fast-forward (diverged branch?) - leaving as-is"
    else
        ok "updated to $(git -C "$SKILLS_DIR" rev-parse --short HEAD)"
    fi
elif [[ -e "$SKILLS_DIR" ]]; then
    error "$SKILLS_DIR exists but is not a git checkout - move it aside first"
else
    info "cloning $REPO_URL -> $SKILLS_DIR"
    mkdir -p "$(dirname "$SKILLS_DIR")"
    git clone --quiet "$REPO_URL" "$SKILLS_DIR"
    ok "cloned $(git -C "$SKILLS_DIR" rev-parse --short HEAD)"
fi

[[ -d "$SKILLS_DIR/skills" ]] || error "skills directory missing from $SKILLS_DIR"
warn "Quit and restart OpenCode for the Cloudflare skills to load."
