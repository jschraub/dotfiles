#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GTK4_SETTINGS_SRC="$SCRIPT_DIR/gtk-4.0/.config/gtk-4.0/settings.ini"
GTK4_SETTINGS_DEST="$HOME/.config/gtk-4.0/settings.ini"
info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*"; exit 1; }

# ── Install packages ──
install_packages() {
    local pkgs=(nautilus polkit-gnome gvfs gvfs-mtp gvfs-smb)
    local missing=()
    for pkg in "${pkgs[@]}"; do
        pacman -Qi "$pkg" &>/dev/null || missing+=("$pkg")
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        info "All packages already installed"
        return
    fi

    info "Installing: ${missing[*]}"
    sudo pacman -Syy --needed "${missing[@]}"
}

# ── Install GTK4 settings (hides CSD buttons via gtk-decoration-layout) ──
install_gtk4_css() {
    info "Installing GTK4 settings via stow..."
    mkdir -p "$HOME/.config/gtk-4.0"
    # Remove existing real file so stow can create the symlink
    rm -f "$GTK4_SETTINGS_DEST"
    stow -d "$SCRIPT_DIR" -t "$HOME" gtk-4.0
}

# ── Configure Nautilus via gsettings ──
configure_nautilus() {
    info "Configuring Nautilus..."

    # Dark mode
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'

    # List view with compact rows by default
    gsettings set org.gnome.nautilus.preferences default-folder-viewer 'list-view'
    gsettings set org.gnome.nautilus.list-view default-zoom-level 'small'

    # Hide CSD titlebar buttons (redundant under Hyprland)
    gsettings set org.gnome.desktop.wm.preferences button-layout ''

    # Show hidden files
    gsettings set org.gnome.nautilus.preferences show-hidden-files true

    # Sort by name ascending
    gsettings set org.gnome.nautilus.preferences default-sort-order 'name'

    # Search only local files (faster)
    gsettings set org.gnome.nautilus.preferences recursive-search 'local-only'
}

# ── Switch Hyprland file manager variable ──
update_hyprland_conf() {
    local conf="$HOME/.config/hypr/hyprland.conf"

    if [[ ! -f "$conf" ]]; then
        warn "Hyprland config not found at $conf — skipping"
        return
    fi

    if grep -q '^\$fileManager = nautilus' "$conf"; then
        info "Hyprland already set to nautilus"
        return
    fi

    info "Updating Hyprland fileManager to nautilus..."
    sed -i 's/^\$fileManager = .*/$fileManager = nautilus/' "$conf"
}

# ── Switch polkit agent ──
update_polkit_agent() {
    local conf="$HOME/.config/hypr/hyprland.conf"

    if [[ ! -f "$conf" ]]; then
        warn "Hyprland config not found at $conf — skipping"
        return
    fi

    if grep -q 'polkit-gnome' "$conf"; then
        info "Hyprland already using polkit-gnome"
        return
    fi

    info "Switching polkit agent to polkit-gnome..."
    sed -i 's|exec-once = /usr/lib/polkit-kde-authentication-agent-1|exec-once = /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1|' "$conf"
}

# ── Main ──
info "Setting up Nautilus..."
install_packages
install_gtk4_css
configure_nautilus
update_hyprland_conf
update_polkit_agent

info "Done!"
echo ""
info "Summary:"
echo "  - Packages installed: nautilus polkit-gnome gvfs gvfs-mtp gvfs-smb"
echo "  - Dark mode enabled"
echo "  - Default view: list (compact)"
echo "  - GTK4 settings: gtk-decoration-layout=: (CSD buttons hidden)"
echo "  - Hidden files: shown"
echo "  - Sort order: name ascending"
echo "  - Hyprland \$fileManager: nautilus"
echo "  - Hyprland polkit agent: polkit-gnome"
echo ""
warn "Restart Hyprland for polkit agent change to take effect."
