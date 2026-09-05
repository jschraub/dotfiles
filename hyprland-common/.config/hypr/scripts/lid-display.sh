#!/bin/sh
# Reconcile the internal laptop panel with the physical lid, then rebuild
# waybar's per-output bars.
#
# Called from four places that must all agree: the two lid-switch binds, the
# monitor.added event, and hypridle's after_sleep_cmd.
#
# Three separate facts make a plain pair of lid binds insufficient:
#
#  1. `hyprctl keyword` is REJECTED under the Lua config parser -- it answers
#     "keyword can't work with non-legacy parsers. Use eval.". The old lid binds
#     shelled out to exactly that, so from the Lua migration onward they were
#     silent no-ops and the panel never actually turned off. Monitor changes go
#     through `hyprctl eval` + hl.monitor() now.
#
#  2. Switch binds fire only on TRANSITIONS, and the Lid Switch input device is
#     destroyed and recreated across suspend/resume. A lid already shut when the
#     device reappears emits no event at all, so an event-driven design cannot be
#     correct on its own. Read the real state instead of trusting the edge.
#
#  3. Waybar builds one bar per output at startup and does not reliably rebuild
#     the set when an output disappears and comes back. Losing the external
#     monitor's bar while the invisible internal panel keeps its own is exactly
#     what a closed lid plus a resume produces.
#
# No-op on machines with no lid and no internal panel (the desktop).
set -eu

# eDP-2 from /sys/class/drm/card2-eDP-2/status. Hyprland names outputs after the
# DRM connector, so nothing here needs a hardcoded per-machine output name.
connector() {
    c=${1%/status}
    c=${c##*/}
    printf '%s\n' "${c#*-}"
}

mon() {
    hyprctl eval "hl.monitor({ output = \"$1\", disabled = $2 })" >/dev/null 2>&1 || true
}

# Must test status, not just the glob: the hybrid-GPU laptop exposes an eDP
# connector on BOTH cards (card1-eDP-1 on the NVIDIA side is permanently
# disconnected) and only the connected one is the real panel.
internal_panel() {
    for d in /sys/class/drm/card*-eDP-*/status; do
        [ -r "$d" ] || continue
        if [ "$(cat "$d")" = connected ]; then
            connector "$d"
            return 0
        fi
    done
    return 0
}

# Mirrors logind's own "docked" test: any connected non-internal connector.
count_external() {
    n=0
    for s in /sys/class/drm/card*-*/status; do
        [ -r "$s" ] || continue
        case "$(connector "$s")" in
            eDP*|LVDS*|DSI*|Writeback*) continue ;;
        esac
        if [ "$(cat "$s")" = connected ]; then
            n=$((n + 1))
        fi
    done
    printf '%s\n' "$n"
}

lid_state() {
    for f in /proc/acpi/button/lid/*/state; do
        if [ -r "$f" ]; then
            cat "$f"
            return 0
        fi
    done
    return 0
}

# `hyprctl monitors` lists enabled outputs only, so a hit means "currently on".
panel_enabled() {
    hyprctl monitors 2>/dev/null | grep -q "^Monitor $1 "
}

# Leaving the session: hand every connected head back to the greeter, including a
# panel we had disabled for the lid. Without this the exit keybind can drop the
# greeter onto a display that is still switched off.
if [ "${1:-}" = "--all-on" ]; then
    for s in /sys/class/drm/card*-*/status; do
        [ -r "$s" ] || continue
        [ "$(cat "$s")" = connected ] || continue
        c=$(connector "$s")
        case "$c" in Writeback*) continue ;; esac
        mon "$c" false
    done
    exit 0
fi

panel=$(internal_panel)
state=$(lid_state)

if [ -n "$panel" ] && [ -n "$state" ]; then
    case "$state" in
        *closed*)
            # Never blank the only display. With no external head attached, a lid
            # close is logind's business (it suspends) rather than ours.
            if [ "$(count_external)" -gt 0 ] && panel_enabled "$panel"; then
                mon "$panel" true
            fi
            ;;
        *)
            panel_enabled "$panel" || mon "$panel" false
            ;;
    esac
fi

# Runs on every reconcile rather than only when the panel changed: a plain
# external-monitor hotplug moves no lid but still loses the bar.
#
# Serialized, and NOT with a plain `pkill -USR2`. Two SIGUSR2 landing inside one
# reload cycle kills waybar outright -- observed with signals 45ms apart, where
# the second "Reloading..." never completed and the process was gone. This script
# runs from four places and monitor.added fires once per output, so back-to-back
# invocations are the normal case, not the edge case. flock queues them and the
# sleep holds the lock until the reload has settled.
RUNTIME="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
(
    flock 9 || exit 0
    if pgrep -x waybar >/dev/null 2>&1; then
        pkill -USR2 -x waybar 2>/dev/null || true
        sleep 2
    else
        # No waybar to signal: first run of the session, or it died. Either way
        # an output event is a good moment to get the bar back. 9>&- so the new
        # process does not inherit -- and hold -- the lock.
        setsid waybar >/dev/null 2>&1 9>&- &
    fi
) 9>"$RUNTIME/lid-display.waybar.lock"

exit 0
