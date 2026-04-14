#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THEME_NAME="catppuccin-tolkien"
THEME_SRC="$SCRIPT_DIR/sddm-setup/usr/share/sddm/themes/$THEME_NAME"
THEME_DEST="/usr/share/sddm/themes/$THEME_NAME"
SDDM_CONF_SRC="$SCRIPT_DIR/sddm-setup/etc/sddm.conf.d/theme.conf"
SDDM_CONF_DEST="/etc/sddm.conf.d/theme.conf"

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*"; exit 1; }

# ── Dependency check ──
check_deps() {
    local missing=()
    command -v sddm >/dev/null 2>&1 || missing+=("sddm")
    # Wayland compositor for the SDDM greeter (also pulls in qt6-5compat, qt6-svg)
    pacman -Qi kwin &>/dev/null || missing+=("kwin")
    local fonts
    fonts="$(fc-list : family)"
    if ! echo "$fonts" | grep -qi "CaskaydiaCove"; then
        missing+=("ttf-cascadia-code-nerd (CaskaydiaCove Nerd Font)")
    fi
    if [[ ${#missing[@]} -gt 0 ]]; then
        warn "Missing dependencies: ${missing[*]}"
        read -rp "Install missing packages with pacman? [Y/n] " ans
        if [[ "${ans,,}" != "n" ]]; then
            local pkgs=()
            for dep in "${missing[@]}"; do
                case "$dep" in
                    sddm) pkgs+=("sddm") ;;
                    kwin) pkgs+=("kwin") ;;
                    *CaskaydiaCove*) pkgs+=("ttf-cascadia-code-nerd") ;;
                esac
            done
            sudo pacman -S --needed "${pkgs[@]}"
        fi
    fi
}

# ── Install theme ──
install_theme() {
    info "Installing SDDM theme '$THEME_NAME'..."

    if [[ ! -d "$THEME_SRC" ]]; then
        error "Theme source not found at $THEME_SRC"
    fi

    sudo mkdir -p "$THEME_DEST"
    sudo cp -r "$THEME_SRC"/* "$THEME_DEST"/
    sudo chmod -R a+rX "$THEME_DEST"
    info "Theme files copied to $THEME_DEST"

    sudo mkdir -p /etc/sddm.conf.d
    sudo cp "$SDDM_CONF_SRC" "$SDDM_CONF_DEST"
    info "SDDM config installed to $SDDM_CONF_DEST"

    # Remove /etc/sddm.conf if it conflicts with our drop-in
    # (e.g. it sets DisplayServer=x11 which causes blank screens on Wayland-only systems)
    if [[ -f /etc/sddm.conf ]]; then
        if grep -qi 'DisplayServer=x11' /etc/sddm.conf 2>/dev/null; then
            warn "Found /etc/sddm.conf with DisplayServer=x11 — this conflicts with Wayland greeter"
            info "Backing up to /etc/sddm.conf.bak and removing..."
            sudo cp /etc/sddm.conf /etc/sddm.conf.bak
            sudo rm /etc/sddm.conf
            info "Removed conflicting /etc/sddm.conf (backup at /etc/sddm.conf.bak)"
        fi
    fi
}

# ── Enable SDDM service ──
enable_sddm() {
    # Verify sddm.service exists as a systemd unit
    if ! systemctl list-unit-files sddm.service 2>/dev/null | grep -q sddm; then
        error "sddm.service not found — is the sddm package installed?"
    fi

    if systemctl is-active --quiet sddm; then
        info "SDDM is already running"
        return
    fi

    if systemctl is-enabled --quiet sddm 2>/dev/null; then
        info "SDDM is already enabled"
        return
    fi

    local dm_symlink="/etc/systemd/system/display-manager.service"
    if [[ -L "$dm_symlink" ]]; then
        local current_dm current_dm_target
        current_dm_target="$(readlink "$dm_symlink")"
        current_dm="$(basename "$current_dm_target" .service)"

        # Check if the current DM is already SDDM (possibly via an alias)
        if [[ "$current_dm" == "sddm" ]] || [[ "$current_dm_target" == *"sddm"* ]]; then
            info "SDDM is already the active display manager"
            return
        fi

        # Save previous DM for recovery
        echo "$current_dm" | sudo tee /etc/sddm.conf.d/.previous-dm >/dev/null

        warn "Current display manager: $current_dm"
        echo ""
        warn "╔══════════════════════════════════════════════════════════════╗"
        warn "║  RECOVERY: if you get a blank screen after reboot:         ║"
        warn "║  1. Press Ctrl+Alt+F2 to switch to a TTY                   ║"
        warn "║  2. Log in with your username and password                  ║"
        warn "║  3. Run:                                                    ║"
        warn "║     sudo systemctl disable sddm                            ║"
        warn "║     sudo systemctl enable $current_dm$(printf '%*s' $((26 - ${#current_dm})) '')║"
        warn "║     sudo reboot                                            ║"
        warn "╚══════════════════════════════════════════════════════════════╝"
        echo ""

        read -rp "Disable $current_dm and enable SDDM instead? [Y/n] " ans
        if [[ "${ans,,}" != "n" ]]; then
            info "Disabling $current_dm..."
            sudo systemctl disable "$current_dm"
            info "Enabling SDDM..."
            sudo systemctl enable sddm
        else
            warn "Skipping — SDDM will not be enabled"
        fi
    else
        info "No display manager currently enabled"
        info "Enabling SDDM service..."
        sudo systemctl enable sddm
    fi
}

# ── Stow hyprlock config ──
stow_hyprlock() {
    if command -v stow >/dev/null 2>&1; then
        info "Stowing hyprlock config..."
        cd "$SCRIPT_DIR"
        stow -R hyprlock
        info "hyprlock config stowed"
    else
        warn "GNU Stow not found — skipping hyprlock stow (install with: pacman -S stow)"
    fi
}

# ── Preview ──
preview_theme() {
    read -rp "Preview the theme in test mode? [y/N] " ans
    if [[ "${ans,,}" == "y" ]]; then
        info "Launching SDDM greeter in test mode..."
        sddm-greeter-qt6 --test-mode --theme "$THEME_DEST" || \
            sddm-greeter --test-mode --theme "$THEME_DEST" 2>/dev/null || \
            warn "Could not launch test mode. You'll see the theme on next login."
    fi
}

# ── Verify SDDM configuration ──
verify_sddm() {
    info "Verifying SDDM configuration..."
    local ok=true

    # Check theme directory exists and is readable
    if [[ ! -f "$THEME_DEST/Main.qml" ]]; then
        warn "Theme Main.qml not found at $THEME_DEST"
        ok=false
    fi

    if [[ ! -f "$THEME_DEST/background.jpg" ]]; then
        warn "Theme background.jpg not found at $THEME_DEST"
        ok=false
    fi

    # Ensure SDDM config points to our theme
    if [[ -f /etc/sddm.conf.d/theme.conf ]]; then
        if ! grep -q "Current=$THEME_NAME" /etc/sddm.conf.d/theme.conf; then
            warn "SDDM config does not reference theme '$THEME_NAME'"
            ok=false
        fi
        if ! grep -q "DisplayServer=wayland" /etc/sddm.conf.d/theme.conf; then
            warn "SDDM config does not set DisplayServer=wayland"
            ok=false
        fi
    else
        warn "SDDM theme config not found at /etc/sddm.conf.d/theme.conf"
        ok=false
    fi

    # Warn if /etc/sddm.conf overrides the Wayland setting
    if [[ -f /etc/sddm.conf ]] && grep -qi 'DisplayServer=x11' /etc/sddm.conf 2>/dev/null; then
        warn "/etc/sddm.conf still forces DisplayServer=x11 — this will override the drop-in!"
        ok=false
    fi

    if $ok; then
        info "SDDM configuration looks good"
    else
        warn "There may be issues with the SDDM configuration — check warnings above"
    fi
}

# ── Main ──
main() {
    info "Catppuccin Tolkien SDDM Theme Installer"
    echo ""
    check_deps
    install_theme
    enable_sddm
    verify_sddm
    stow_hyprlock
    echo ""
    info "Done! Theme '$THEME_NAME' is now active."
    if [[ -f /etc/sddm.conf.d/.previous-dm ]]; then
        local prev_dm
        prev_dm="$(cat /etc/sddm.conf.d/.previous-dm)"
        info "Previous DM saved. To revert: sudo systemctl disable sddm && sudo systemctl enable $prev_dm && sudo reboot"
    fi
    preview_theme
}

main
