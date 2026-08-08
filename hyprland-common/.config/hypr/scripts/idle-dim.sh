#!/bin/sh
# Dim the monitor backlight on idle without ever brightening it.
#
# hypridle's stock `brightnessctl -s set 10` is an absolute set, not a floor:
# when the screen is already below 10 it RAISES brightness on idle. Guard the
# dim so it only ever lowers.
#
# The restore is gated on a flag written by the dim. Without that gate, a cycle
# where the guard declined to dim would still run `brightnessctl -r` and replay
# a stale saved value from a previous cycle — a worse version of the same bug.
# The flag also makes multiple restore paths (the 150s listener and the 330s
# dpms listener) idempotent: whichever fires first restores and clears it.
set -eu

TARGET=10
RUNTIME="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
FLAG="$RUNTIME/hypridle-dimmed"

# The LED matrix daemon (~/code/matrix) follows screen brightness, and takes
# over a panel with a gauge when *you* change it. udev cannot tell a thumb from
# a timer, so this marks the writes below as automatic and the daemon suppresses
# the takeover for them — without it a full-panel gauge lights up at the exact
# moment you walk away from the machine.
#
# Touched before AND after each write: the kernel emits the uevent during the
# write, but the daemon reads it asynchronously, so marking only one side leaves
# a race in which an automatic change looks deliberate.
#
# Entirely best-effort. Dimming must work whether or not anything is listening.
MARKER="$RUNTIME/matrixd/brightness-auto"
mark() { mkdir -p "${MARKER%/*}" 2>/dev/null && : > "$MARKER" 2>/dev/null || true; }

case "${1:-}" in
  dim)
    if [ "$(brightnessctl -m g)" -gt "$TARGET" ]; then
      mark
      brightnessctl -q -s set "$TARGET"
      mark
      : > "$FLAG"
    fi
    ;;
  restore)
    if [ -e "$FLAG" ]; then
      mark
      # -q does not suppress output for -r in brightnessctl 0.5.1; keep stderr.
      brightnessctl -q -r >/dev/null
      mark
      rm -f "$FLAG"
    fi
    ;;
  *)
    echo "usage: ${0##*/} dim|restore" >&2
    exit 2
    ;;
esac
