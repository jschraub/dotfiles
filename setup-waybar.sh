#!/usr/bin/env bash
# Prefer stable Waybar >=0.16.0; atomically replace waybar-git when available.
# --stable refuses a Git fallback. No -R step, -Sy, or automatic bar restart.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/setup.sh"
set -euo pipefail
MIN_WAYBAR=0.16.0

waybar_version() {
    local result
    result="$(LC_ALL=C pacman -Q waybar 2>/dev/null)" || return 1
    printf '%s\n' "${result#* }"
}

install_waybar() {
    local installed available git_installed=0
    installed="$(waybar_version || true)"
    available="$(LC_ALL=C pacman -Si waybar 2>/dev/null | awk '/^Version[[:space:]]*:/ {print $3; exit}' || true)"
    pacman -Q waybar-git &>/dev/null && git_installed=1

    if [[ -n "$installed" && "$(vercmp "$installed" "$MIN_WAYBAR")" -ge 0 && "$git_installed" == 0 ]]; then
        info "Stable Waybar $installed already supports Lua workspace clicks"
    elif [[ -n "$available" && "$(vercmp "$available" "$MIN_WAYBAR")" -ge 0 ]]; then
        info "Installing stable Waybar $available (Lua support requires >=$MIN_WAYBAR)"
        if [[ "$git_installed" == 1 ]]; then
            warn "Replacing waybar-git in ONE transaction; approve its removal when pacman asks."
        fi
        sudo pacman -S --needed "waybar>=$MIN_WAYBAR"
        installed="$(waybar_version || true)"
        [[ -n "$installed" && "$(vercmp "$installed" "$MIN_WAYBAR")" -ge 0 ]] \
            || error "Stable Waybar installation was not confirmed; no removal was attempted separately"
        if pacman -Q waybar-git &>/dev/null; then
            error "waybar-git is still installed; resolve the package transaction before continuing"
        fi
    elif [[ "$stable_only" == 1 ]]; then
        error "Sync database has no Waybar >=$MIN_WAYBAR. Run a normal full system update (sudo pacman -Syu), then retry. Existing Waybar was left installed."
    elif [[ "$git_installed" == 1 ]]; then
        info "Keeping waybar-git: stable >=$MIN_WAYBAR is not in the local sync database yet"
    else
        [[ -n "$AUR_HELPER" ]] || error "Stable repo Waybar is too old; update with sudo pacman -Syu or install paru/yay for waybar-git"
        warn "Stable repo Waybar is too old; installing waybar-git for Lua workspace clicks"
        "$AUR_HELPER" -S --needed waybar-git
    fi
}

main() {
    stable_only=0
    case "${1:-}" in
        '') ;;
        --stable) stable_only=1 ;;
        -h|--help) echo 'Usage: ./setup-waybar.sh [--stable]'; return ;;
        *) error 'Usage: ./setup-waybar.sh [--stable]' ;;
    esac
    [[ $# -le 1 ]] || error 'Too many arguments'
    command -v pacman >/dev/null || error 'pacman is required'
    command -v vercmp >/dev/null || error 'vercmp (pacman) is required'
    install_waybar
    # The first registry dependency is handled above, including upgrades/conflicts.
    local deps
    read -ra deps <<< "${PKGS[waybar]}"
    pkg_install "${deps[@]:1}"
    command -v stow >/dev/null || pkg_install stow
    safe_stow waybar
    info 'Waybar configured. Reload at a convenient time: pkill -USR2 -x waybar'
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
