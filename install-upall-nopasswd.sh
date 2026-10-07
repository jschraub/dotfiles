#!/usr/bin/env bash
# Install the root-owned pacman gate and the matching passwordless sudo rule for
# upall. The gate, rather than sudoers argument globs, enforces its small policy.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/upall-setup/usr/local/libexec/upall-pacman"
DESTINATION=/usr/local/libexec/upall-pacman
SUDOERS_DESTINATION=/etc/sudoers.d/upall-pacman
USER_NAME="$(id -un)"

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*" >&2; exit 1; }

[[ -f "$SOURCE" ]] || error "missing $SOURCE"
command -v visudo >/dev/null || error "visudo is required"

rule_file="$(mktemp)"
trap 'rm -f "$rule_file"' EXIT
printf '%s ALL=(root) NOPASSWD: %s\n' "$USER_NAME" "$DESTINATION" >"$rule_file"
visudo -cf "$rule_file" >/dev/null || error "generated sudoers rule is invalid"

info "This permits $USER_NAME to run only $DESTINATION as root without a password."
info "The root-owned gate permits upall's non-interactive repository/AUR updates only."
read -r -p 'Install this passwordless upall policy? [y/N] ' answer
[[ "${answer,,}" == y || "${answer,,}" == yes ]] || error "aborted"

# Authenticate once while installing. The installed NOPASSWD rule is tested only
# after this credential is cleared, so a cached credential cannot mask a mistake.
sudo -v
sudo install -d -o root -g root -m 755 /usr/local/libexec
sudo install -o root -g root -m 755 "$SOURCE" "$DESTINATION"
sudo install -o root -g root -m 440 "$rule_file" "$SUDOERS_DESTINATION"
sudo visudo -cf "$SUDOERS_DESTINATION" >/dev/null

sudo -k
sudo -n "$DESTINATION" --upall-authorization-check
sudo -k

info "Passwordless upall is installed and verified. Run: upall"
