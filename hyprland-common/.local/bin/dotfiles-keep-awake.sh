#!/usr/bin/env bash
# A logind idle inhibitor owned by the user manager, NOT by a shell/bar surface.
# Transient (not enabled at login), survives bar reloads, and exits on logout
# even when the user manager lingers. Explicit/manual suspend remains available.
set -euo pipefail

unit=dotfiles-keep-awake.service
who=dotfiles-keep-awake

identity() {
    local stat rest
    IFS= read -r stat < "/proc/$1/stat" || return 1
    rest=${stat##*) }
    local fields
    read -ra fields <<< "$rest"
    [[ ${fields[0]} != Z ]] || return 1
    printf '%s\n' "${fields[19]}" # starttime (field 22), protects against PID reuse
}

inhibited() {
    systemd-inhibit --list --json=short --no-pager |
        jq -e --arg who "$who" --argjson uid "$(id -u)" \
            'any(.[]; .who == $who and .uid == $uid and .what == "idle" and .mode == "block")' >/dev/null
}

case "${1:-status}" in
    hold)
        pid=$2
        birth=$3
        logger --tag dotfiles-power -- "Keep awake acquired; watching compositor pid=$pid"
        while [[ "$(identity "$pid" 2>/dev/null || true)" == "$birth" ]]; do
            sleep 2
        done
        logger --tag dotfiles-power -- 'Keep awake released: compositor session ended'
        ;;
    status)
        if ! inhibitors=$(systemd-inhibit --list --json=short --no-pager 2>/dev/null); then
            printf '%s\n' '{"text":"!","class":"error","tooltip":"Keep awake: cannot query logind"}'
            exit 0
        fi
        if ! active=$(jq -r --arg who "$who" --argjson uid "$(id -u)" \
            'if type != "array" then error("expected inhibitor array") else
                any(.[]; .who == $who and .uid == $uid and .what == "idle" and .mode == "block")
             end' <<< "$inhibitors" 2>/dev/null) || [[ "$active" != true && "$active" != false ]]; then
            printf '%s\n' '{"text":"!","class":"error","tooltip":"Keep awake: invalid logind response"}'
            exit 0
        fi
        if [[ "$active" == true ]]; then
            printf '%s\n' '{"text":"󰅶","class":"activated","tooltip":"Full cup: keep awake\nSurvives bar reloads; manual suspend still allowed\nClick to allow idle sleep"}'
        else
            printf '%s\n' '{"text":"󰛊","class":"deactivated","tooltip":"Empty cup: allow idle sleep\nClick to keep awake"}'
        fi
        ;;
    toggle)
        exec 9>"${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/dotfiles-keep-awake.lock"
        flock 9
        if systemctl --user is-active --quiet "$unit"; then
            systemctl --user stop "$unit"
            logger --tag dotfiles-power -- 'Keep awake disabled by user'
            exit 0
        fi
        # Refuse ambiguous multi-compositor sessions instead of binding to the
        # wrong lifetime. No compositor IPC or session environment is required.
        mapfile -t pids < <(pgrep -u "$(id -u)" -x Hyprland || true)
        if [[ ${#pids[@]} != 1 ]]; then
            logger --tag dotfiles-power -- 'Cannot enable keep awake: expected one Hyprland process'
            exit 1
        fi
        pid=${pids[0]}
        birth=$(identity "$pid")
        systemd-run --user --quiet --collect --service-type=exec \
            --unit="$unit" --description='Keep awake for this Hyprland session' \
            /usr/bin/systemd-inhibit --no-ask-password --what=idle --mode=block \
            --who="$who" --why='Keep awake selected in desktop shell' \
            "$(readlink -f "$0")" hold "$pid" "$birth"
        # Do not report success merely because the launcher was executed: wait
        # for logind to confirm that the actual inhibitor has been acquired.
        for ((i=0; i<30; i++)); do
            if inhibited; then exit 0; fi
            sleep 0.1
        done
        systemctl --user stop "$unit" || true
        logger --tag dotfiles-power -- 'ERROR: keep-awake inhibitor acquisition failed'
        exit 1
        ;;
    *) echo "usage: ${0##*/} status|toggle" >&2; exit 2 ;;
esac
