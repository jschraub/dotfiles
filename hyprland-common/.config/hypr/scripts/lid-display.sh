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

# libaquamarine SEGFAULTS when an output is disabled while the session is still
# coming up, and it takes Hyprland with it. That is not theoretical: doing this in
# the greeter made the machine unbootable -- Hyprland died, regreet lost its
# Wayland display mid-init and exited without creating a session, greetd restarted
# it, and every iteration of that loop was a modeset the external monitor showed as
# signal dropping and returning.
#
# monitor.added fires once per output during startup, so without this guard a
# lid-closed session's very first act is exactly that disable. Skip the monitor
# half until the compositor has settled; the deferred call from hyprland.start
# clears this window and does the real reconcile.
compositor_settled() {
    hpid=$(pgrep -x -o Hyprland 2>/dev/null || true)
    [ -n "$hpid" ] || return 1
    hage=$(ps -o etimes= -p "$hpid" 2>/dev/null | tr -dc 0-9)
    [ -n "$hage" ] || return 1
    [ "$hage" -ge 10 ]
}

panel=$(internal_panel)
state=$(lid_state)

if [ -n "$panel" ] && [ -n "$state" ] && compositor_settled; then
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
# Two hard rules here, both learned by breaking them:
#
#  1. NEVER start waybar. An earlier version started one when it saw none, which
#     raced Hyprland's own `sleep 1 && waybar` autostart and produced TWO bars at
#     login, one of which then died. Autostart owns starting waybar; this owns
#     signalling it.
#
#  2. Never signal a waybar that is still starting. It builds its per-output bars
#     during the first seconds, and a reload landing in that window aborts the
#     process (seen as waybar dumping core moments after login). A young waybar
#     also needs no reload -- it is already enumerating the current outputs.
#
# Serialized for the same reason: two SIGUSR2 inside one reload cycle kills waybar
# outright, observed 45ms apart. This script runs from several places and
# monitor.added fires once per output, so back-to-back invocations are normal.
pid=$(pgrep -x -o waybar 2>/dev/null || true)
if [ -n "$pid" ]; then
    age=$(ps -o etimes= -p "$pid" 2>/dev/null | tr -dc 0-9)
    if [ -n "$age" ] && [ "$age" -ge 8 ]; then
        RUNTIME="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
        (
            flock 9 || exit 0
            pkill -USR2 -x waybar 2>/dev/null || true
            sleep 2
        ) 9>"$RUNTIME/lid-display.waybar.lock"
    fi
fi

exit 0
