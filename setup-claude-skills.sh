#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$SCRIPT_DIR/claude-skills"
MARKETPLACE="claude-skills"
PLUGIN="claude-skills@claude-skills"
info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*"; exit 1; }

# ── Preconditions ──
command -v claude &>/dev/null || error "claude CLI not found on PATH"
[[ -f "$SKILLS_DIR/.claude-plugin/marketplace.json" ]] \
    || error "marketplace.json not found in $SKILLS_DIR"

# ── Register the local marketplace (directory source, served in-place) ──
register_marketplace() {
    if claude plugin marketplace list 2>/dev/null | grep -q "$MARKETPLACE"; then
        info "Marketplace '$MARKETPLACE' already configured"
        return
    fi
    info "Adding marketplace from $SKILLS_DIR..."
    claude plugin marketplace add "$SKILLS_DIR"
}

# ── Install + enable the plugin ──
install_plugin() {
    if claude plugin list 2>/dev/null | grep -q "$PLUGIN"; then
        info "Plugin '$PLUGIN' already installed"
        return
    fi
    info "Installing plugin $PLUGIN..."
    claude plugin install "$PLUGIN"
}

# ── Main ──
info "Setting up Claude skills..."
register_marketplace
install_plugin

info "Done!"
echo ""
info "Summary:"
echo "  - Marketplace: $MARKETPLACE (directory source → $SKILLS_DIR)"
echo "  - Plugin:      $PLUGIN (user scope, enabled)"
echo ""
warn "Restart Claude Code for the skills to load in a session."
