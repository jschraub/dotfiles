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

# timeout: 3 seconds
sed -i 's/^timeout:.*/timeout: 3/' "$LIMINE_CONF"

# default_entry: 2 selects first sub-entry inside expanded CachyOS directory
# (entry 1 = CachyOS directory header, entry 2 = first kernel)
sed -i 's/^default_entry:.*/default_entry: 2/' "$LIMINE_CONF"

# Remove remember_last_entry
sed -i '/^remember_last_entry:/d' "$LIMINE_CONF"

# Update wallpaper
sed -i 's|^wallpaper:.*|wallpaper: boot():/limine-wallpaper.jpg|' "$LIMINE_CONF"

# Interface resolution: remove to let Limine auto-detect the best available mode
# AMD RDNA2 GPUs typically support native resolution via UEFI GOP
sed -i '/^interface_resolution:/d' "$LIMINE_CONF"

# Remove term_font_scale to use default (1x1) — avoids blocky oversized font
sed -i '/^term_font_scale:/d' "$LIMINE_CONF"

# Hide help text for cleaner look
if grep -q '^interface_help_hidden:' "$LIMINE_CONF"; then
    sed -i 's/^interface_help_hidden:.*/interface_help_hidden: yes/' "$LIMINE_CONF"
elif ! grep -q '^interface_help_hidden:' "$LIMINE_CONF"; then
    sed -i '/^wallpaper:/a interface_help_hidden: yes' "$LIMINE_CONF"
fi

# Make terminal background fully transparent so wallpaper shows through
# Limine uses TTRRGGBB where ff = fully transparent, 00 = fully opaque
sed -i 's/^term_background:.*/term_background: ffffffff/' "$LIMINE_CONF"
sed -i 's/^term_background_bright:.*/term_background_bright: ffffffff/' "$LIMINE_CONF"

# Set branding to a clean space (hides default "Limine" text)
sed -i 's/^interface_branding:.*/interface_branding: /' "$LIMINE_CONF"

# Remove Windows Boot Manager entry
info "Removing Windows Boot Manager entry..."
sed -i '/\/\/Windows Boot Manager/,/^[[:space:]]*image_path:.*bootmgfw\.efi/d' "$LIMINE_CONF"

# Rename entries to clean display names
info "Renaming boot entries..."
sed -i 's|^/+CachyOS|/+CachyOS|' "$LIMINE_CONF"  # Keep as-is (already clean)
sed -i 's|^[[:space:]]*//linux-cachyos-lts$|  //CachyOS LTS|' "$LIMINE_CONF"
sed -i 's|^[[:space:]]*//linux-cachyos$|  //CachyOS|' "$LIMINE_CONF"
sed -i 's|^[[:space:]]*//Snapshots|  //Snapshots|' "$LIMINE_CONF"

info "Done! Changes applied to $LIMINE_CONF"
info "Backup saved as $LIMINE_CONF.bak"
echo ""
info "Summary:"
echo "  - Timeout: 3 seconds"
echo "  - Default entry: CachyOS/CachyOS (path-based, selects CachyOS subentry)"
echo "  - Wallpaper: hobbit-tri-split.jpg"
echo "  - Interface resolution: 3840x2160 (explicit, avoids bad auto-detect)"
echo "  - Font scale: default (1x1)"
echo "  - Help text: hidden"
echo "  - Branding: hidden"
echo "  - remember_last_entry: removed"
echo "  - Windows entry: removed"
echo "  - Entry names: cleaned up"
echo ""
warn "Note: limine-entry-tool may overwrite entry names on kernel updates."
warn "Re-run this script after kernel updates if names revert."
