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
FLAG="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hypridle-dimmed"

case "${1:-}" in
  dim)
    if [ "$(brightnessctl -m g)" -gt "$TARGET" ]; then
      brightnessctl -q -s set "$TARGET"
      : > "$FLAG"
    fi
    ;;
  restore)
    if [ -e "$FLAG" ]; then
      # -q does not suppress output for -r in brightnessctl 0.5.1; keep stderr.
      brightnessctl -q -r >/dev/null
      rm -f "$FLAG"
    fi
    ;;
  *)
    echo "usage: ${0##*/} dim|restore" >&2
    exit 2
    ;;
esac
