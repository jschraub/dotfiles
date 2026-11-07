#!/usr/bin/env bash
# Password PAM on every host; optional native fingerprint auth through fprintd.
# No reader/service -> password-only, silently. Never put pam_fprintd in PAM.
set -euo pipefail
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
if [[ $# == 0 && -r "$config_home/dotfiles/lock-screen" ]] && \
    [[ "$(< "$config_home/dotfiles/lock-screen")" == atelier ]]; then
    exec "$HOME/.local/bin/desktop-lock"
fi
mode="${HYPRLOCK_FINGERPRINT:-}"
if [[ -z "$mode" && -r "$config_home/dotfiles/hyprlock-fingerprint" ]]; then
    read -r mode < "$config_home/dotfiles/hyprlock-fingerprint" || true
fi
mode="${mode:-auto}"
case "$mode" in auto|on|off) ;; *) echo 'Invalid fingerprint policy; locking with password only' >&2; mode=off ;; esac
fingerprint=false
if [[ "$mode" != off ]] && command -v busctl >/dev/null; then
    devices="$(busctl --system --timeout=2 call net.reactivated.Fprint /net/reactivated/Fprint/Manager \
        net.reactivated.Fprint.Manager GetDevices 2>/dev/null || true)"
    [[ "$devices" != *'/net/reactivated/Fprint/Device/'* ]] || fingerprint=true
fi
if [[ "${1:-}" == --check ]]; then
    printf 'fingerprint=%s (policy=%s); password authentication always enabled\n' "$fingerprint" "$mode"
    exit 0
fi
[[ $# == 0 ]] || { echo 'Usage: lock.sh [--check]' >&2; exit 1; }
[[ -n "${XDG_RUNTIME_DIR:-}" ]] || { echo 'XDG_RUNTIME_DIR is required' >&2; exit 1; }
exec 9>"$XDG_RUNTIME_DIR/dotfiles-hyprlock.lock"
flock -n 9 || exit 0
pgrep -u "$(id -u)" -x hyprlock >/dev/null && exit 0
config="$(mktemp "$XDG_RUNTIME_DIR/hyprlock.XXXXXX.conf")"
trap 'rm -f "$config"' EXIT
printf 'source = %s/hypr/hyprlock.conf\nauth:pam:enabled = true\nauth:pam:module = hyprlock\nauth:fingerprint:enabled = %s\n' \
    "$config_home" "$fingerprint" > "$config"
hyprlock --config "$config"
