#!/bin/bash

# 1. Get physical width, height, and scale of the active monitor from Hyprland
MON_INFO=$(hyprctl -j monitors | jq -r '.[] | select(.focused) | "\(.width) \(.height) \(.scale)"')
PHYS_W=$(echo "$MON_INFO" | awk '{print $1}')
PHYS_H=$(echo "$MON_INFO" | awk '{print $2}')
SCALE=$(echo "$MON_INFO" | awk '{print $3}')

# 2. Calculate logical Wayland coordinates (Fixes offset if you use scaling)
LOGICAL_W=$(echo "$PHYS_W $SCALE" | awk '{printf "%.0f", $1 / $2}')
LOGICAL_H=$(echo "$PHYS_H $SCALE" | awk '{printf "%.0f", $1 / $2}')

# 3. Define your exact button and layout preferences
BTN_SIZE=360
GAP=10
COLS=2
ROWS=2

# 4. Calculate the total size of the tightened grid
GRID_W=$(( (BTN_SIZE * COLS) + (GAP * (COLS - 1)) ))
GRID_H=$(( (BTN_SIZE * ROWS) + (GAP * (ROWS - 1)) ))

# 5. Calculate the exact outer margins needed to center the grid
MARGIN_X=$(( (LOGICAL_W - GRID_W) / 2 ))
MARGIN_Y=$(( (LOGICAL_H - GRID_H) / 2 ))

# 6. Launch wlogout with the dynamic margins and the 10px internal gaps
wlogout -b $COLS -c $GAP -r $GAP -L $MARGIN_X -R $MARGIN_X -T $MARGIN_Y -B $MARGIN_Y
