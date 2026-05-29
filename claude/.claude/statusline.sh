#!/usr/bin/env bash
# Claude Code statusline — Catppuccin Mocha powerline with rounded left cap
# Reads JSON from stdin, prints a single styled line.

input=$(cat)

# ── Catppuccin Mocha palette (truecolor R;G;B) ───────────────────────────────
cat_rosewater="245;224;220"
cat_flamingo="242;205;205"
cat_pink="245;194;231"
cat_mauve="203;166;247"
cat_red="243;139;168"
cat_maroon="235;160;172"
cat_peach="250;179;135"
cat_yellow="249;226;175"
cat_green="166;227;161"
cat_teal="148;226;213"
cat_sky="137;220;235"
cat_sapphire="116;199;236"
cat_blue="137;180;250"
cat_lavender="180;190;254"
cat_crust="17;17;27"

# ── Style ────────────────────────────────────────────────────────────────────
reset=$'\e[0m'
bold=$'\e[1m'

# Per-segment background colors (pastel Catppuccin hues)
bg_dir="$cat_blue"          # folder
bg_git_clean="$cat_green"   # git, clean
bg_git_dirty="$cat_peach"   # git, dirty
bg_time="$cat_sapphire"     # clock
bg_claude="$cat_mauve"      # claude / model
bg_rate="$cat_yellow"       # rate limits

# Per-segment icon foreground — same dark Crust as text (bold for emphasis)
icon_fg_dir="$cat_crust"
icon_fg_git_clean="$cat_crust"
icon_fg_git_dirty="$cat_crust"
icon_fg_time="$cat_crust"
icon_fg_claude="$cat_crust"
icon_fg_rate="$cat_crust"

fg_text="$cat_crust"             # dark text on every pastel bg

# Powerline glyphs (Nerd Font)
cap_left=$'\xee\x82\xb6'     # nf-pl-right_soft_divider (rounded left cap)
divider=$'\xee\x82\xb0'      # nf-pl-left_hard_divider  (chevron between/end)

# Icons (Nerd Font) — \u for BMP (4-hex), \U for SMP (8-hex)
# Each icon constant ends with exactly one trailing space.
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

bgs+=("$bg_dir");      icon_fgs+=("$icon_fg_dir");        icons+=("$icon_folder"); texts+=("$cwd_display")
if [ -n "$git_branch" ]; then
    bgs+=("$git_bg");  icon_fgs+=("$git_icon_fg");        icons+=("$icon_git");    texts+=("$git_branch")
fi
bgs+=("$bg_time");     icon_fgs+=("$icon_fg_time");       icons+=("$icon_time");   texts+=("$time_now")
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
    # Text in dark Crust on the same pastel bg
    out+="$(set_bg "$bg")$(set_fg "$fg_text")${texts[i]} ${reset}"

    if (( i < n - 1 )); then
        # Chevron blends into next segment's bg
        out+="$(set_bg "${bgs[i+1]}")$(set_fg "$bg")${divider}${reset}"
    else
        # Final chevron fades to terminal default
        out+="$(set_fg "$bg")${divider}${reset}"
    fi
done

printf '%s\n' "$out"
