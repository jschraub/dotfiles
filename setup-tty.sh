#!/usr/bin/env bash
# Linux virtual-console setup. Run as your normal user: ./setup-tty.sh
# Installs Terminus, preserves keyboard settings, and links TTY-only Fish config.
# No compositor/getty restart; the font is applied now only if run from a VT.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_LINE='test -f ~/.config/fish/tty.fish; and source ~/.config/fish/tty.fish'

if [[ $# -ne 0 ]]; then
    echo 'Usage: ./setup-tty.sh (run as your normal user, not with sudo)'
    [[ "$1" == --help || "$1" == -h ]]
    exit
fi
if [[ $EUID -eq 0 ]]; then
    echo 'Run as your normal user; the script uses sudo for system changes.' >&2
    exit 1
fi

missing=()
for pkg in terminus-font fish; do
    pacman -Q "$pkg" &>/dev/null || missing+=("$pkg")
done
if [[ ${#missing[@]} -gt 0 ]]; then
    sudo pacman -S --needed "${missing[@]}"
fi

# Prepare the update before touching /etc. Keep all non-FONT settings/comments.
temp="$(mktemp)"
trap 'rm -f "$temp"' EXIT
input=/dev/null
[[ ! -f /etc/vconsole.conf ]] || input=/etc/vconsole.conf
awk '
    /^[[:space:]]*FONT[[:space:]]*=/ {
        if (!found++) print "FONT=ter-v16n"
        next
    }
    { print }
    END { if (!found) print "FONT=ter-v16n" }
' "$input" > "$temp"
if ! cmp -s "$temp" /etc/vconsole.conf; then
    if [[ -e /etc/vconsole.conf ]]; then
        sudo cp -a /etc/vconsole.conf "/etc/vconsole.conf.pre-tty.$(date +%Y%m%d%H%M%S%N)"
    fi
    sudo install -m 644 "$temp" /etc/vconsole.conf
fi

fish_dir="$HOME/.config/fish"
mkdir -p "$fish_dir"
src="$SCRIPT_DIR/fish/.config/fish/tty.fish"
dest="$fish_dir/tty.fish"
if [[ "$(readlink -f "$dest")" != "$(readlink -f "$src")" ]]; then
    if [[ -e "$dest" || -L "$dest" ]]; then
        mv "$dest" "$dest.pre-tty.$(date +%Y%m%d%H%M%S%N)"
    fi
    ln -s "$src" "$dest"
fi
config="$fish_dir/config.fish"
if ! grep -qF "$SOURCE_LINE" "$config" 2>/dev/null; then
    if [[ -e "$config" ]]; then
        cp -a "$config" "$config.pre-tty.$(date +%Y%m%d%H%M%S%N)"
    fi
    printf '\n# Linux console overrides (after vendor configuration).\n%s\n' "$SOURCE_LINE" >> "$config"
fi

console="$(tty 2>/dev/null || true)"
if [[ "$console" =~ ^/dev/tty[0-9]+$ ]]; then
    sudo setfont -C "$console" ter-v16n
else
    echo 'Font saved for boot. To apply now, run sudo setfont ter-v16n from TTY2.'
fi
echo 'TTY setup complete. Run exec fish from TTY2 to load the prompt and palette.'
