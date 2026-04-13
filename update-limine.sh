#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOT_DIR="/boot"
LIMINE_CONF="$BOOT_DIR/limine.conf"
BG_SRC="$SCRIPT_DIR/backgrounds/.config/backgrounds/tolkien/hobbit-tri-split.jpg"

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*"; exit 1; }

[[ $EUID -eq 0 ]] || error "This script must be run with sudo"

[[ -f "$LIMINE_CONF" ]] || error "limine.conf not found at $LIMINE_CONF"
[[ -f "$BG_SRC" ]] || error "Background image not found at $BG_SRC"

# Backup current config
info "Backing up current limine.conf..."
cp "$LIMINE_CONF" "$LIMINE_CONF.bak"

# Copy background image to boot partition
info "Copying background image to boot partition..."
cp "$BG_SRC" "$BOOT_DIR/limine-wallpaper.jpg"

# Update limine.conf settings (top section only)
info "Updating limine.conf..."

# timeout: 5 → 3
sed -i 's/^timeout:.*/timeout: 3/' "$LIMINE_CONF"

# default_entry: 2 → 1
sed -i 's/^default_entry:.*/default_entry: 1/' "$LIMINE_CONF"

# Remove remember_last_entry
sed -i '/^remember_last_entry:/d' "$LIMINE_CONF"

# Update wallpaper
sed -i 's|^wallpaper:.*|wallpaper: boot():/limine-wallpaper.jpg|' "$LIMINE_CONF"

# Set interface_resolution for cleaner font rendering on high-DPI
# Use native res if available, limine will scale the font
if ! grep -q '^interface_resolution:' "$LIMINE_CONF"; then
    sed -i '/^wallpaper:/a interface_resolution: 3840x2160' "$LIMINE_CONF"
fi

# Set branding to a clean space (hides default "Limine" text)
sed -i 's/^interface_branding:.*/interface_branding: /' "$LIMINE_CONF"

# Remove Windows Boot Manager entry
info "Removing Windows Boot Manager entry..."
sed -i '/\/\/Windows Boot Manager/,/^[[:space:]]*image_path:.*bootmgfw\.efi/d' "$LIMINE_CONF"

info "Done! Changes applied to $LIMINE_CONF"
info "Backup saved as $LIMINE_CONF.bak"
echo ""
info "Summary:"
echo "  - Timeout: 3 seconds"
echo "  - Default entry: 1 (CachyOS)"
echo "  - Wallpaper: hobbit-tri-split.jpg"
echo "  - Interface resolution: 3840x2160"
echo "  - Branding: hidden"
echo "  - remember_last_entry: removed"
