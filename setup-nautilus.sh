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
    local pkgs=(nautilus polkit gvfs gvfs-mtp gvfs-smb python inter-font breeze-icons)
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
    # Shared installer backs up conflicting real files AND old theme symlinks.
    # Also installs GTK3 and neutral/amber theme assets for advanced settings apps.
    python3 "$SCRIPT_DIR/scripts/apply_theme.py" --no-runtime
}

# ── Configure Nautilus via gsettings ──
configure_nautilus() {
    info "Configuring Nautilus..."

    # Dark mode
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
    gsettings set org.gnome.desktop.interface gtk-theme 'Atelier'
    if gsettings list-keys org.gnome.desktop.interface | grep -qx accent-color; then
        gsettings set org.gnome.desktop.interface accent-color 'yellow'
    fi

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

# ── Main ──
info "Setting up Nautilus..."
install_packages
install_gtk4_css
configure_nautilus

info "Done!"
echo ""
info "Summary:"
echo "  - Packages installed: nautilus polkit gvfs gvfs-mtp gvfs-smb"
echo "  - Dark mode enabled"
echo "  - Default view: list (compact)"
echo "  - GTK4 settings: gtk-decoration-layout=: (CSD buttons hidden)"
echo "  - Hidden files: shown"
echo "  - Sort order: name ascending"
