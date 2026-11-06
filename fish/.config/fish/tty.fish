# Sourced at the END of config.fish, after vendor aliases and prompt setup.
if not status is-interactive; or test "$TERM" != linux; or not isatty stdout
    return
end

# Do not advertise truecolor on the Linux console. Leave TERM=linux intact.
set -e COLORTERM
set -g fish_color_normal normal
set -g fish_color_command blue
set -g fish_color_param white
set -g fish_color_quote green
set -g fish_color_error red
set -g fish_color_comment brblack
set -g fish_color_operator yellow
set -g fish_color_escape cyan
set -g fish_color_autosuggestion brblack
set -g fish_color_cwd blue
set -g fish_color_valid_path --underline
set -g fish_color_redirection cyan
set -g fish_color_end green
set -g fish_color_search_match --background=brblack
set -g fish_pager_color_prefix cyan
set -g fish_pager_color_completion normal
set -g fish_pager_color_description yellow
set -g fish_pager_color_selected_background --background=brblack

function fish_prompt
    set -l last_status $status
    set_color cyan
    printf '%s@%s ' $USER (hostname -s)
    set_color blue
    printf '%s' (prompt_pwd)
    set_color normal
    if test $last_status -ne 0
        printf ' [%s]' $last_status
    end
    printf ' > '
end

function fish_right_prompt
end

function fish_mode_prompt
end

function fish_greeting
end

if command -q eza
    alias ls='eza -al --color=auto --group-directories-first --icons=never'
    alias la='eza -a --color=auto --group-directories-first --icons=never'
    alias ll='eza -l --color=auto --group-directories-first --icons=never'
    alias lt='eza -aT --color=auto --group-directories-first --icons=never'
end

# Catppuccin Mocha's 16 ANSI colors, using Linux console palette escapes.
set -l palette 1e1e2e f38ba8 a6e3a1 f9e2af 89b4fa f5c2e7 94e2d5 bac2de \
               585b70 f38ba8 a6e3a1 f9e2af 89b4fa f5c2e7 94e2d5 cdd6f4
for i in (seq 1 16)
    printf '\e]P%x%s' (math $i - 1) $palette[$i]
end
