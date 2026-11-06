# CachyOS fish base (interactive abbreviations, theme, etc.)
status is-interactive && source /usr/share/cachyos-fish-config/cachyos-config.fish

# Login shell is bash (so VS Code Remote-SSH's POSIX bootstrap works); bash execs
# fish for interactive sessions. Point $SHELL back at fish so tools that spawn
# $SHELL get fish. Exported, so child processes inherit it.
set -gx SHELL (command -v fish)
set -gx EDITOR "$HOME/.local/bin/desktop-editor --wait"
set -gx VISUAL "$EDITOR"

# Empty greeting
function fish_greeting
end

# Interactive-only setup. Kept out of non-interactive shells so Tide's prompt
# subshell (a `fish -c`, which re-sources this file) stays fast — otherwise these
# interactive integrations would run on every prompt.
# Exported vars set here are inherited by that subshell, so nothing is lost.
if status is-interactive
    # fzf key bindings
    fzf --fish | source

    # Prompt: Tide (installed via fisher; themed in conf.d/tide_theme.fish as a
    # Atelier Amber powerline). On a new machine `fisher update` reads
    # ../fish_plugins and installs it; if it doesn't pick Tide up, run:
    #   fisher install ilancosman/tide@v6

    # node version manager (adds a cd hook)
    fnm env --use-on-cd | source

    # Do not export the GitHub PAT globally: GH_TOKEN takes precedence over
    # gh's saved OAuth credential and this PAT is limited to only five repos.
    # The keyring secret remains available for tools that explicitly need it.
    set -e GH_TOKEN
    set -e GITHUB_TOKEN
end

# Apply after vendor colors; the TTY override below still uses named ANSI colors.
set -g fish_color_normal $atelier_text
set -g fish_color_command $atelier_accent
set -g fish_color_param $atelier_text
set -g fish_color_quote $atelier_good
set -g fish_color_error $atelier_danger
set -g fish_color_comment $atelier_faint
set -g fish_color_autosuggestion $atelier_faint
set -g fish_color_operator $atelier_orange
set -g fish_color_escape $atelier_orange
set -g fish_color_redirection $atelier_accent
set -g fish_color_end $atelier_accent
set -g fish_color_search_match --background=$atelier_selection
set -g fish_pager_color_prefix $atelier_accent
set -g fish_pager_color_completion $atelier_text
set -g fish_pager_color_description $atelier_muted
set -g fish_pager_color_selected_background --background=$atelier_selection

# After CachyOS aliases and Tide: console-only overrides, never GUI terminals.
test -f ~/.config/fish/tty.fish; and source ~/.config/fish/tty.fish
