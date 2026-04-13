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
    info "Theme files copied to $THEME_DEST"

    sudo mkdir -p /etc/sddm.conf.d
    sudo cp "$SDDM_CONF_SRC" "$SDDM_CONF_DEST"
    info "SDDM config installed to $SDDM_CONF_DEST"
}

# ── Enable SDDM service ──
enable_sddm() {
    if systemctl is-active --quiet sddm; then
        info "SDDM is already running"
    else
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

# ── Main ──
main() {
    info "Catppuccin Tolkien SDDM Theme Installer"
    echo ""
    check_deps
    install_theme
    enable_sddm
    stow_hyprlock
    echo ""
    info "Done! Theme '$THEME_NAME' is now active."
    preview_theme
}

main
