#!/usr/bin/env bash
# Install the password-only PAM stack for hyprlock.
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

[[ -f "$SRC" ]] || error "missing $SRC"

# A broken auth stack locks you out of your own lock screen, so keep the original.
if [[ -f "$DEST" ]] && [[ ! -f "$DEST.orig" ]]; then
    sudo cp -a "$DEST" "$DEST.orig"
    info "Backed up existing stack to $DEST.orig"
fi

sudo install -m 644 -o root -g root "$SRC" "$DEST"
info "Installed $DEST"

# Failed unlock attempts from the fprintd bug may still have the account locked.
if sudo faillock --user "$USER" 2>/dev/null | grep -qE '^\s*[0-9]{4}-'; then
    warn "Clearing recorded auth failures for $USER (faillock)"
    sudo faillock --user "$USER" --reset
fi

cat <<'MSG'

Verify BEFORE logging out, from a terminal you can get back to:

    hyprlock

Unlock it with your password. If that works you are done. If it does not,
restore with:

    sudo cp -a /etc/pam.d/hyprlock.orig /etc/pam.d/hyprlock

MSG
