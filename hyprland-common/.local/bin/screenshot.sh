#!/bin/sh
# screenshot.sh -- area / window / output screenshots via grimblast.
#
# Requires: grimblast-git hyprpicker  (paru -S grimblast-git hyprpicker)
#   grimblast  -- the capture wrapper (uses grim + slurp + hyprctl)
#   hyprpicker -- freezes the screen while you drag the selection box
#
# Usage: screenshot.sh {area|active|output}
#   area    drag-to-select a region (screen frozen during selection)
#   active  the currently focused window
#   output  the currently focused monitor
#
# Every capture is copied to the clipboard AND saved as a PNG to
# ~/Pictures/Screenshots/, then a notification is fired.

mode="${1:-area}"

# grimblast reads XDG_SCREENSHOTS_DIR first; point it at a dedicated folder and
# make sure that folder exists (grimblast does not create it itself).
export XDG_SCREENSHOTS_DIR="$HOME/Pictures/Screenshots"
mkdir -p "$XDG_SCREENSHOTS_DIR"

# Freezing only matters while manually selecting a region; instant captures
# (active/output) gain nothing from it and would spawn hyprpicker needlessly.
freeze=""
[ "$mode" = "area" ] && freeze="--freeze"

exec grimblast $freeze --notify copysave "$mode"
