#!/bin/bash
# network-menu.sh -- wofi-driven NetworkManager picker for the waybar network module.
#
# Requires: networkmanager fuzzel libnotify  (installed by setup.sh's waybar package)
#   nmcli        -- every piece of network state and every action
#   fuzzel       -- the menu itself, and the masked password prompt
#   notify-send  -- connect / failure toasts (swaync renders them)
#
# fuzzel rather than wofi because wofi only activates an entry on double click
# and has no click configuration at all (no such option exists in 1.5.3, its
# last release). fuzzel activates on a single left click, and quits on right
# click. Geometry and colours live in ../../.config/fuzzel/network.ini.
#
# Usage: network-menu.sh          (bound to waybar's network module on-click)
#
# Design notes, i.e. why this is not the obvious three-liner:
#
#   * The list is read from NetworkManager's *cache* (--rescan no) so the menu
#     opens instantly. There is an explicit Rescan row for when you want the
#     truth; rescanning on every open would add 2-5s to every click and make
#     this feel worse than the nmtui popup it replaces.
#
#   * Nerd Font glyphs are \U escapes, not literal PUA bytes. Literal glyphs do
#     not reliably survive being written into files by tooling here, and a
#     silently-stripped glyph is an annoying bug to chase.
#
#   * Wifi passwords go to nmcli on *stdin* (--ask), never in argv, so they
#     never land in /proc/<pid>/cmdline. Verified: nmcli --ask reads piped
#     input, it does not require a TTY.
#
#   * A failed connect to a NEW network leaves a saved profile holding the WRONG
#     password. The next attempt would then take the "saved" path and fail
#     forever without ever prompting. So failed profiles are deleted; see
#     connect_to().
#
#   * VPN state is not ours to change: ProtonVPN's daemon owns it and its
#     NetworkManager profiles are ephemeral. See build_menu().
#
#   * The menu is built in *this* shell, not in a pipeline. The action lookup
#     tables are shell arrays, and a pipeline would build them in a subshell
#     where they would evaporate before dispatch.

set -u

# ---------------------------------------------------------------- configuration

readonly WAIT=15                   # seconds before a connect attempt counts as failed
readonly NOTIFY_ID=9047            # fixed id => "Connecting..." is REPLACED by the result
readonly WAYBAR_SIGNAL=8           # matches "signal": 8 on the custom/vpn module
readonly MAX_DEPTH=3               # cap on failure-driven menu reopens
readonly SSID_COL=22               # display width of the ssid column

# Anchoring (top-right, under the bar), sizing and colours all live here.
readonly FUZZEL_CONF="$HOME/.config/fuzzel/network.ini"

# Plain HTTP on purpose: a captive portal cannot transparently intercept HTTPS
# without a certificate error, so an https probe would never get redirected.
readonly PROBE_URL="http://nmcheck.gnome.org/check_network_status.txt"

readonly BROWSER="zen-browser"
readonly VPN_APP="protonvpn-app"
ADVANCED_CMD=(ghostty --title=nmtui-float -e nmtui)

# Nerd Font glyphs (nf-md-*), all verified present in CaskaydiaCove Nerd Font.
readonly G_WIFI_4=$'\U000f0928'    # wifi-strength-4
readonly G_WIFI_3=$'\U000f0925'    # wifi-strength-3
readonly G_WIFI_2=$'\U000f0922'    # wifi-strength-2
readonly G_WIFI_1=$'\U000f091f'    # wifi-strength-1
readonly G_WIFI_OFF=$'\U000f092d'  # wifi-strength-off-outline
readonly G_RADIO_OFF=$'\U000f05a9' # wifi          (shown on the "turn wifi on" row)
readonly G_VPN=$'\U000f0582'       # vpn
readonly G_WEB=$'\U000f059f'       # web
readonly G_REFRESH=$'\U000f0453'   # refresh
readonly G_COG=$'\U000f0493'       # cog

readonly SEP="$(printf "$(printf '\\u2500%.0s' {1..34})")"
readonly US=$'\x1f'                # field separator that cannot occur in an ssid

# ------------------------------------------------------------------- primitives

notify() { # notify <urgency> <summary> [body]
    notify-send -r "$NOTIFY_ID" -a Network -u "$1" "$2" "${3:-}"
}

# nmcli -t escapes ':' as '\:' and '\' as '\\'. Undo that, in that order.
unescape() { printf '%s' "$1" | sed -e 's/\\:/:/g' -e 's/\\\\/\\/g'; }

menu() { # menu <prompt> ; reads entries on stdin, prints the chosen line
    fuzzel --dmenu --config "$FUZZEL_CONF" --prompt "$1  "
}

ask_password() { # ask_password <ssid>
    # Nothing on stdin, so there is no list to match against -- fuzzel's dmenu
    # mode prints the typed string when it matches no entry, which is exactly
    # the behaviour a password prompt needs. --lines=0 collapses the (empty)
    # list so only the input row is drawn.
    : | fuzzel --dmenu --config "$FUZZEL_CONF" --password --lines=0 \
               --prompt "Password for $1  "
}

# NetworkManager's cached verdict -- returns instantly. `connectivity check`
# (used only after connecting) re-probes and blocks.
connectivity() { nmcli -t networking connectivity 2>/dev/null; }

# 'portal' means NM's probe was redirected. A portal that simply drops the probe
# yields 'limited' instead -- which is the exact "connected but no internet"
# case where the sign-in escape hatch is most needed. So both count.
needs_signin() {
    local state; state=$(connectivity)
    [[ $state == portal || $state == limited ]]
}

signal_bars() {
    local s=$1
    if   (( s >= 76 )); then printf '%b' '▂▄▆█'
    elif (( s >= 51 )); then printf '%b' '▂▄▆_'
    elif (( s >= 26 )); then printf '%b' '▂▄__'
    else                     printf '%b' '▂___'
    fi
}

signal_icon() {
    local s=$1
    if   (( s >= 76 )); then printf '%s' "$G_WIFI_4"
    elif (( s >= 51 )); then printf '%s' "$G_WIFI_3"
    elif (( s >= 26 )); then printf '%s' "$G_WIFI_2"
    else                     printf '%s' "$G_WIFI_1"
    fi
}

reopen() { # re-run ourselves after a failure, but never unboundedly
    local depth=$(( ${NETMENU_DEPTH:-0} + 1 ))
    (( depth >= MAX_DEPTH )) && exit 0
    NETMENU_DEPTH=$depth exec "$0"
}

# ------------------------------------------------------------------------ state

declare -A SAVED=()        # ssid -> 1, for wifi profiles whose name is the ssid
declare -A ACT_KIND=()     # menu line -> action verb
declare -A ACT_ARG=()      # menu line -> ssid / connection name
declare -A ACT_SEC=()      # menu line -> security string ('' == open)
declare -A ACT_SAVED=()    # menu line -> yes|no
declare -a MENU_LINES=()   # the menu, in render order

VPN_ACTIVE_NAME=""

collect_profiles() {
    local type name
    while IFS=: read -r type name; do
        [[ $type == 802-11-wireless ]] && SAVED[$(unescape "$name")]=1
    done < <(nmcli -t -f TYPE,NAME connection show 2>/dev/null)

    while IFS=: read -r type name; do
        [[ $type == wireguard || $type == vpn ]] || continue
        VPN_ACTIVE_NAME=$(unescape "$name")
        break
    done < <(nmcli -t -f TYPE,NAME connection show --active 2>/dev/null)
}

add_row() { # add_row <line> <kind> <arg> [security] [saved]
    local line=$1
    [[ -n ${ACT_KIND[$line]:-} ]] && return   # first writer wins
    ACT_KIND[$line]=$2
    ACT_ARG[$line]=$3
    ACT_SEC[$line]=${4:-}
    ACT_SAVED[$line]=${5:-no}
    MENU_LINES+=("$line")
}

fmt_row() { # fmt_row <signal> <ssid> <security>
    printf '%s  %-*s %s  %s' \
        "$(signal_icon "$1")" "$SSID_COL" "${2:0:$SSID_COL}" \
        "$(signal_bars "$1")" "${3:-open}"
}

# Current network first and separated, then saved networks by descending signal,
# then unsaved by descending signal.
emit_networks() {
    local inuse signal security ssid raw current="" sig ss
    local -A best=() secof=()
    local -a saved_rows=() other_rows=()

    raw=$(nmcli -t -f IN-USE,SIGNAL,SECURITY,SSID device wifi list --rescan no 2>/dev/null)

    # Pass 1. The 4th read variable soaks up the rest of the line, so an ssid
    # containing ':' survives intact (still escaped, hence unescape).
    # IN-USE is '*' when active and a single SPACE otherwise -- not empty.
    # An ssid can legitimately appear more than once (mesh, repeaters, and the
    # active AP is listed separately), so keep the strongest reading of each and
    # work out the current ssid independently of that dedup.
    while IFS=: read -r inuse signal security ssid; do
        ssid=$(unescape "$ssid")
        [[ -z $ssid ]] && continue                       # hidden network
        [[ $inuse == '*' ]] && current=$ssid
        if [[ -z ${best[$ssid]:-} ]] || (( signal > ${best[$ssid]} )); then
            best[$ssid]=$signal
            secof[$ssid]=$security
        fi
    done <<<"$raw"

    if [[ -n $current ]]; then
        add_row "$(printf '%s  %-*s %s' \
            "$(signal_icon "${best[$current]}")" "$SSID_COL" \
            "${current:0:$SSID_COL}" 'connected')" noop ""
        MENU_LINES+=("$SEP")
    fi

    # Pass 2: split into saved / unsaved, each sorted by signal descending.
    for ss in "${!best[@]}"; do
        [[ $ss == "$current" ]] && continue
        if [[ -n ${SAVED[$ss]:-} ]]; then
            saved_rows+=("${best[$ss]}${US}${ss}")
        else
            other_rows+=("${best[$ss]}${US}${ss}")
        fi
    done

    while IFS=$US read -r sig ss; do
        [[ -z $ss ]] && continue
        add_row "$(fmt_row "$sig" "$ss" "${secof[$ss]}")" connect "$ss" "${secof[$ss]}" yes
    done < <(printf '%s\n' ${saved_rows[@]+"${saved_rows[@]}"} | sort -t"$US" -k1,1nr)

    while IFS=$US read -r sig ss; do
        [[ -z $ss ]] && continue
        add_row "$(fmt_row "$sig" "$ss" "${secof[$ss]}")" connect "$ss" "${secof[$ss]}" no
    done < <(printf '%s\n' ${other_rows[@]+"${other_rows[@]}"} | sort -t"$US" -k1,1nr)
}

# ---------------------------------------------------------------------- actions

# Point the browser at the probe URL and let the portal hijack it. The VPN is
# deliberately NOT touched -- warn instead, and let the toggle one row up in the
# same menu do the work if you want it.
open_portal() {
    if [[ -n $VPN_ACTIVE_NAME ]]; then
        notify normal "VPN is up -- portal may not load" \
            "$VPN_ACTIVE_NAME is routing your traffic. Turn it off from this menu, then sign in."
    fi
    setsid -f "$BROWSER" --new-window "$PROBE_URL" >/dev/null 2>&1
}

# After a successful connect, give NM a moment to decide whether there is really
# internet on the other side, and surface the portal if there is not.
check_portal_after_connect() {
    local i state
    for i in {1..6}; do
        state=$(nmcli -t networking connectivity check 2>/dev/null)
        [[ $state == full ]] && return
        if [[ $state == portal || $state == limited ]]; then
            open_portal
            return
        fi
        sleep 1
    done
}

connect_to() { # connect_to <ssid> <security> <saved:yes|no>
    local ssid=$1 sec=$2 saved=$3
    local out rc pass

    notify low "Connecting to $ssid"

    if [[ $saved == yes ]]; then
        out=$(nmcli --wait "$WAIT" connection up id "$ssid" 2>&1); rc=$?
    elif [[ -z $sec ]]; then
        out=$(nmcli --wait "$WAIT" device wifi connect "$ssid" 2>&1); rc=$?
    else
        pass=$(ask_password "$ssid")
        [[ -z $pass ]] && exit 0        # cancelled -- stay silent
        out=$(printf '%s\n' "$pass" | nmcli --wait "$WAIT" device wifi connect "$ssid" --ask 2>&1)
        rc=$?
    fi

    if (( rc == 0 )); then
        notify normal "Connected to $ssid"
        check_portal_after_connect
        return
    fi

    # Delete the bad-password profile this attempt just created, otherwise the
    # retry takes the "saved" path and silently replays the wrong secret.
    if [[ $saved == no ]] && nmcli -t -f NAME connection show 2>/dev/null \
        | sed -e 's/\\:/:/g' | grep -qxF "$ssid"; then
        nmcli connection delete id "$ssid" >/dev/null 2>&1
    fi

    notify critical "Failed to connect to $ssid" "$(printf '%s' "$out" | tail -n1)"
    reopen
}

# Hand VPN state changes to the app that owns them. Deliberately fire-and-forget:
# the tunnel comes up seconds later, and custom/vpn's poll picks it up.
launch_vpn_app() {
    setsid -f "$VPN_APP" >/dev/null 2>&1
}

# Only reached when the Proton app is absent, i.e. for ordinary persistent VPN
# profiles that NetworkManager alone is responsible for.
toggle_vpn() { # toggle_vpn <name>
    local name=$1
    if [[ $name == "$VPN_ACTIVE_NAME" ]]; then
        if nmcli --wait "$WAIT" connection down id "$name" >/dev/null 2>&1; then
            notify normal "VPN disconnected" "$name"
        else
            notify critical "Could not disconnect VPN" "$name"
        fi
    else
        if nmcli --wait "$WAIT" connection up id "$name" >/dev/null 2>&1; then
            notify normal "VPN connected" "$name"
        else
            notify critical "Could not connect VPN" "$name"
        fi
    fi
    pkill -RTMIN+$WAYBAR_SIGNAL waybar 2>/dev/null
}

# ------------------------------------------------------------------- the menu

build_menu() {
    if [[ $(nmcli radio wifi 2>/dev/null) != enabled ]]; then
        add_row "$G_RADIO_OFF  Turn wifi on" wifi_on  ""
        add_row "$G_COG  Advanced (nmtui)"   advanced ""
        return
    fi

    emit_networks
    # Only close off the network block if it actually rendered something --
    # otherwise (nothing else in range, or nothing in range at all) we would
    # stack two separators against each other, or lead with a stray one.
    if (( ${#MENU_LINES[@]} > 0 )) && [[ ${MENU_LINES[-1]} != "$SEP" ]]; then
        MENU_LINES+=("$SEP")
    fi

    needs_signin && add_row "$G_WEB  Sign in to network" portal ""

    # ProtonVPN's daemon creates its NetworkManager profiles on connect and
    # DELETES them again on disconnect. So enumerating saved VPN profiles finds
    # nothing at all while the tunnel is down, and a naive toggle row would be
    # invisible precisely when you want to switch the VPN on. Worse, tearing a
    # Proton-managed connection down with `nmcli connection down` goes around
    # the daemon and leaves its app convinced it is still connected.
    #
    # So when the Proton app is installed it owns both directions and this row
    # simply opens it. Without it, fall back to driving ordinary (persistent)
    # VPN profiles directly, which is the correct behaviour anywhere else.
    if command -v "$VPN_APP" >/dev/null 2>&1; then
        if [[ -n $VPN_ACTIVE_NAME ]]; then
            add_row "$G_VPN  $VPN_ACTIVE_NAME  (up)" vpn_app ""
        else
            add_row "$G_VPN  Connect VPN" vpn_app ""
        fi
    else
        local type name state
        while IFS=: read -r type name; do
            [[ $type == wireguard || $type == vpn ]] || continue
            name=$(unescape "$name")
            state=down
            [[ $name == "$VPN_ACTIVE_NAME" ]] && state=up
            add_row "$G_VPN  $name  ($state)" vpn "$name"
        done < <(nmcli -t -f TYPE,NAME connection show 2>/dev/null)
    fi

    add_row "$G_REFRESH  Rescan"         rescan   ""
    add_row "$G_WIFI_OFF  Turn wifi off" wifi_off ""
    add_row "$G_COG  Advanced (nmtui)"   advanced ""
}

main() {
    collect_profiles
    build_menu                 # populates MENU_LINES and ACT_* in THIS shell

    local choice
    choice=$(printf '%s\n' ${MENU_LINES[@]+"${MENU_LINES[@]}"} | menu "Network")
    [[ -z $choice ]] && exit 0

    case "${ACT_KIND[$choice]:-}" in
        connect)  connect_to "${ACT_ARG[$choice]}" "${ACT_SEC[$choice]}" "${ACT_SAVED[$choice]}" ;;
        vpn)      toggle_vpn "${ACT_ARG[$choice]}" ;;
        vpn_app)  launch_vpn_app ;;
        portal)   open_portal ;;
        rescan)   nmcli device wifi list --rescan yes >/dev/null 2>&1
                  NETMENU_DEPTH=0 exec "$0" ;;
        wifi_on)  nmcli radio wifi on  >/dev/null 2>&1 ;;
        wifi_off) nmcli radio wifi off >/dev/null 2>&1 ;;
        advanced) setsid -f "${ADVANCED_CMD[@]}" >/dev/null 2>&1 ;;
        *)        exit 0 ;;    # separator, or a line typed by hand
    esac
}

main "$@"
