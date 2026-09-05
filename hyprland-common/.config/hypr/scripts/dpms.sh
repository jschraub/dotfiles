#!/bin/sh
# Drive DPMS to a definite state: dpms.sh on|off
#
# Two Hyprland facts force this indirection, both introduced by the Lua config:
#
#  1. `hyprctl dispatch dpms on` is a PARSE ERROR. hyprctl evaluates its argument
#     as Lua ("return hl.dispatch(dpms on)"), so the legacy space-separated form
#     fails with "')' expected near 'on'" and the bare `dpms` global is nil. Every
#     dpms call in hypridle.conf was silently failing.
#
#  2. The Lua dispatcher that replaces it, hl.dsp.dpms(...), IGNORES its argument
#     and unconditionally TOGGLES. Verified against "on", "off", true,
#     { state = "on" } and a two-argument form -- every one of them flipped an
#     already-on display OFF. So "turn the screen on" cannot be expressed
#     directly; it has to be read first and toggled only when it disagrees.
#
# Deliberately does not retry after toggling. misc.key_press_enables_dpms turns
# the screen back on by itself, and a retry loop would fight the user for it.
set -eu

target=${1:-}
case "$target" in
    on)  want=1 ;;
    off) want=0 ;;
    *)   echo "usage: ${0##*/} on|off" >&2; exit 2 ;;
esac

# `hyprctl monitors` lists enabled outputs only. There is no per-output form of
# the dispatcher here, so the heads move together and the first one stands for
# the session -- and a disabled internal panel is correctly skipped.
now=$(hyprctl monitors 2>/dev/null | grep -m1 dpmsStatus | tr -dc 0-9)

if [ -z "$now" ]; then
    exit 0            # no enabled monitor; nothing to drive
fi

if [ "$now" != "$want" ]; then
    hyprctl dispatch 'hl.dsp.dpms("toggle")' >/dev/null 2>&1 || true
fi
exit 0
