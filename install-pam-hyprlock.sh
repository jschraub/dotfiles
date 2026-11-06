#!/usr/bin/env bash
# Install safe password PAM on all hosts; native fingerprint auth is optional.
#
# See pam-setup/etc/pam.d/hyprlock for why: the stack Arch ships pulls in
# pam_fprintd, which hyprlock cannot drive alongside a password prompt, so every
# unlock after a resume fails and faillock eventually locks the account.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/pam-setup/etc/pam.d/hyprlock"
DEST="/etc/pam.d/hyprlock"

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*"; exit 1; }

fingerprint=auto
case "${1:-}" in
    '') ;;
    -h|--help) echo 'Usage: ./install-pam-hyprlock.sh [--fingerprint auto|on|off] (run as your normal user)'; exit 0 ;;
    --fingerprint) [[ $# == 2 ]] || error 'Usage: ./install-pam-hyprlock.sh [--fingerprint auto|on|off]'; fingerprint="$2" ;;
    *) error 'Usage: ./install-pam-hyprlock.sh [--fingerprint auto|on|off]' ;;
esac
case "$fingerprint" in auto|on|off) ;; *) error 'Fingerprint policy must be auto, on, or off' ;; esac
[[ $EUID -ne 0 ]] || error 'Run as your normal user; the script requests sudo where needed'
if [[ "$fingerprint" == on ]] && ! command -v fprintd-enroll >/dev/null; then
    error 'For fingerprint unlock, install fprintd and enroll a finger first; auto/off do not require it'
fi

[[ -f "$SRC" ]] || error "missing $SRC"

# A broken auth stack locks you out of your own lock screen, so keep the original.
if [[ -f "$DEST" ]] && [[ ! -f "$DEST.orig" ]]; then
    sudo cp -a "$DEST" "$DEST.orig"
    info "Backed up existing stack to $DEST.orig"
fi

sudo install -m 644 -o root -g root "$SRC" "$DEST"
info "Installed $DEST"

# The wrapper queries fprintd's device list. No reader/service means password-only
# with no fingerprint prompt. Native fingerprint auth never competes for PAM's
# password conversation; authentication on login/sudo is deliberately untouched.
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
mkdir -p "$config_home/dotfiles"
printf '%s\n' "$fingerprint" > "$config_home/dotfiles/hyprlock-fingerprint"
info "Native fingerprint policy: $fingerprint (password unlocking remains enabled)"

# Failed unlock attempts from the fprintd bug may still have the account locked.
if sudo faillock --user "$USER" 2>/dev/null | grep -qE '^\s*[0-9]{4}-'; then
    warn "Clearing recorded auth failures for $USER (faillock)"
    sudo faillock --user "$USER" --reset
fi

cat <<'MSG'

Verify BEFORE logging out, from a terminal you can get back to:

    ~/.config/hypr/scripts/lock.sh

Unlock it with your password. If that works you are done. If it does not,
restore with:

    sudo cp -a /etc/pam.d/hyprlock.orig /etc/pam.d/hyprlock

MSG
