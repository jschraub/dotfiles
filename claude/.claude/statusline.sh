#!/usr/bin/env bash
# Claude Code statusline — Atelier Amber powerline with rounded left cap
# Reads JSON from stdin, prints a single styled line.

input=$(cat)

# The LED matrix daemon's snapshot tap is NOT here on purpose. It lives in
# ~/code/matrix (integration/claude/matrix-statusline-tap.sh) and wraps this
# script via settings.json, so there is exactly one copy of that logic and it
# ships with the public repo rather than being stranded in these dotfiles.

# Shared generated truecolor palette; resolve the real script through Stow.
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/atelier-palette.sh"

# ── Style ────────────────────────────────────────────────────────────────────
reset=$'\e[0m'
bold=$'\e[1m'

# Quiet neutral segments, with amber only on the directory/model and dirty git.
bg_user="$atelier_raised"
bg_time="$atelier_line"
bg_dir="$atelier_accent"
bg_git_clean="$atelier_raised"
bg_git_dirty="$atelier_selection"
bg_claude="$atelier_accent"
bg_rate="$atelier_line"

# Per-segment icon foreground — same dark Crust as text (bold for emphasis)
icon_fg_dir="$atelier_onAccent"
icon_fg_git_clean="$atelier_text"
icon_fg_git_dirty="$atelier_text"
icon_fg_time="$atelier_text"
icon_fg_claude="$atelier_onAccent"
icon_fg_rate="$atelier_text"
icon_fg_user="$atelier_text"

fg_text="$atelier_text"

# Powerline glyphs (Nerd Font)
cap_left=$'\xee\x82\xb6'     # nf-pl-right_soft_divider (rounded left cap)
cap_right=$'\xee\x82\xb4'    # nf-pl-left_soft_divider  (rounded right cap)
divider=$'\xee\x82\xb0'      # nf-pl-left_hard_divider  (chevron between/end)

# Icons (Nerd Font) — \u for BMP (4-hex), \U for SMP (8-hex)
# Each icon constant ends with exactly one trailing space.
icon_user=$'\xef\x80\x87 '           # nf-fa-user
icon_folder=$'\xef\x81\xbb '         # nf-fa-folder
icon_git=$'\xee\x82\xa0 '            # nf-dev-git_branch
icon_time=$'\xef\x80\x97 '           # nf-fa-clock_o
icon_claude=$'\U000F06D4 '           # nf-md-robot
icon_style=$'\U000F050E '            # nf-md-format_paint
icon_ctx=$'\U000F0294 '              # nf-md-database
icon_rate=$'\xef\x83\xa7 '           # nf-fa-bolt
icon_reset=$'\xef\x80\xa1 '          # nf-fa-arrow_right

set_bg() { printf '\e[48;2;%sm' "$1"; }
set_fg() { printf '\e[38;2;%sm' "$1"; }

# ── 0. USER ──────────────────────────────────────────────────────────────────
user_name=$(whoami 2>/dev/null)
[ -z "$user_name" ] && user_name="$USER"

# ── 1. FOLDER ────────────────────────────────────────────────────────────────
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
[ -z "$cwd" ] && cwd="$PWD"
cwd_display="${cwd/#$HOME/\~}"

# ── 2. GIT ───────────────────────────────────────────────────────────────────
git_branch=""
git_bg=""
git_icon_fg=""
if command -v git &>/dev/null; then
    git_branch=$(git -C "$cwd" branch --show-current 2>/dev/null)
    if [ -n "$git_branch" ]; then
        if [ -n "$(git -C "$cwd" --no-optional-locks status --porcelain 2>/dev/null)" ]; then
            git_branch="${git_branch} *"
            git_bg=$bg_git_dirty
            git_icon_fg=$icon_fg_git_dirty
        else
            git_bg=$bg_git_clean
            git_icon_fg=$icon_fg_git_clean
        fi
    fi
fi

# ── 3. TIME ──────────────────────────────────────────────────────────────────
# 24-hour HH:MM — always exactly 5 chars, so the segment width never shifts.
time_now=$(date +%H:%M)

# ── 4. CLAUDE ────────────────────────────────────────────────────────────────
model=$(echo "$input" | jq -r '.model.display_name // empty')
output_style=$(echo "$input" | jq -r '.output_style.name // empty')
ctx_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

claude_text="$model"
if [ -n "$output_style" ] && [ "$output_style" != "default" ] && [ "$output_style" != "Default" ]; then
    claude_text="${claude_text}  ${icon_style}${output_style}"
fi
if [ -n "$ctx_pct" ]; then
    claude_text="${claude_text}  ${icon_ctx}$(printf '%.0f' "$ctx_pct")%"
fi

# ── 5. RATE LIMITS ───────────────────────────────────────────────────────────
five_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
five_resets=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
week_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
rate_text=""
if [ -n "$five_pct" ]; then
    rate_text="5h:$(printf '%.0f' "$five_pct")%"
    if [ -n "$five_resets" ]; then
        reset_hhmm=$(date -d "@$five_resets" +%H:%M 2>/dev/null \
                  || date -d "$five_resets" +%H:%M 2>/dev/null)
        [ -n "$reset_hhmm" ] && rate_text="${rate_text}  ${icon_reset}${reset_hhmm}"
    fi
fi
[ -n "$week_pct" ] && rate_text="${rate_text:+${rate_text}  }7d:$(printf '%.0f' "$week_pct")%"

# ── Collect active segments (bg, icon-fg, icon, text) ────────────────────────
bgs=()
icon_fgs=()
icons=()
texts=()

bgs+=("$bg_user");     icon_fgs+=("$icon_fg_user");       icons+=("$icon_user");   texts+=("$user_name")
bgs+=("$bg_time");     icon_fgs+=("$icon_fg_time");       icons+=("$icon_time");   texts+=("$time_now")
bgs+=("$bg_dir");      icon_fgs+=("$icon_fg_dir");        icons+=("$icon_folder"); texts+=("$cwd_display")
if [ -n "$git_branch" ]; then
    bgs+=("$git_bg");  icon_fgs+=("$git_icon_fg");        icons+=("$icon_git");    texts+=("$git_branch")
fi
bgs+=("$bg_claude");   icon_fgs+=("$icon_fg_claude");     icons+=("$icon_claude"); texts+=("$claude_text")
if [ -n "$rate_text" ]; then
    bgs+=("$bg_rate"); icon_fgs+=("$icon_fg_rate");       icons+=("$icon_rate");   texts+=("$rate_text")
fi

# ── Render ───────────────────────────────────────────────────────────────────
out=""
n=${#bgs[@]}

# Rounded left cap in the first segment's color (no bg)
out+="$(set_fg "${bgs[0]}")${cap_left}${reset}"

for ((i=0; i<n; i++)); do
    bg=${bgs[i]}
    out+="$(set_bg "$bg")"
    # Leading space for breathing room after the chevron / cap
    out+="$(set_fg "$fg_text") ${reset}"
    # Icon in its own color, bold for emphasis
    out+="$(set_bg "$bg")$(set_fg "${icon_fgs[i]}")${bold}${icons[i]}${reset}"
    # Dark text on amber, light text on graphite (same contrast as its icon).
    out+="$(set_bg "$bg")$(set_fg "${icon_fgs[i]}")${texts[i]} ${reset}"

    if (( i < n - 1 )); then
        # Chevron blends into next segment's bg
        out+="$(set_bg "${bgs[i+1]}")$(set_fg "$bg")${divider}${reset}"
    else
        # Final rounded cap fades to terminal default
        out+="$(set_fg "$bg")${cap_right}${reset}"
    fi
done

printf '%s\n' "$out"
