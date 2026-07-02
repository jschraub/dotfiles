# Tide theme — mirrors the Claude Code statusline (Catppuccin Mocha powerline).
# Stow-managed and fully declarative: this file is the single source of truth,
# re-applied on every shell — just edit and open a new shell (or `exec fish`).
# Segments: user → clock → pwd → git → languages → docker (empty ones auto-hidden).
#
# Why `set -g` (not `set -U` + a version guard): Tide keeps its config in
# UNIVERSAL vars and rewrites them on every `fisher install/update` — its
# uninstall event erases all `^_?tide` vars and its install event re-applies the
# built-in `lean` preset (see _tide_init.fish). A guarded "set -U once" scheme
# gets silently clobbered by that, and the guard then blocks re-application —
# which is exactly the "prompt broke after updating dotfiles" bug. Globals
# sidestep it: a global shadows any clobbered universal, writes nothing to disk,
# and — since Tide builds the prompt in a `fish -c` subshell that re-sources
# conf.d — that subshell always sees these values. Do NOT gate this file on
# `status is-interactive`, or the compute subshell wouldn't pick it up.

# Custom git item: branch + dirty '*', green→peach bg, crust text
# (overrides Tide's built-in, which forces white branch text).
function _tide_item_git
    set -l branch (git branch --show-current 2>/dev/null)
    or return
    test -z "$branch"; and return
    set -l changes (git --no-optional-locks status --porcelain 2>/dev/null)
    if test (count $changes) -gt 0
        set -g tide_git_bg_color $tide_git_bg_color_unstable
        _tide_print_item git $tide_git_icon' ' $branch ' *'
    else
        _tide_print_item git $tide_git_icon' ' $branch
    end
end

set -g tide_left_prompt_items user clock pwd git node python rustc go php java docker newline character
set -g tide_right_prompt_items # empty (no right prompt)
set -g tide_left_prompt_prefix 
set -g tide_left_prompt_suffix 
set -g tide_left_prompt_separator_diff_color 
set -g tide_left_prompt_separator_same_color ''
set -g tide_right_prompt_prefix ''
set -g tide_right_prompt_suffix ''
set -g tide_right_prompt_separator_diff_color 
set -g tide_right_prompt_separator_same_color ''
set -g tide_prompt_pad_items true
set -g tide_prompt_add_newline_before true
set -g tide_prompt_transient_enabled false
set -g tide_user_bg_color cba6f7
set -g tide_user_color 11111b
set -g tide_user_icon 
set -g tide_clock_bg_color 89b4fa
set -g tide_clock_color 11111b
set -g tide_clock_icon 
set -g tide_clock_format %H:%M
set -g tide_pwd_bg_color 74c7ec
set -g tide_pwd_color_dirs 11111b
set -g tide_pwd_color_anchors 11111b
set -g tide_pwd_color_truncated_dirs 11111b
set -g tide_pwd_icon 
set -g tide_pwd_icon_home 
set -g tide_pwd_icon_unwritable 
set -g tide_git_bg_color a6e3a1
set -g tide_git_bg_color_unstable fab387
set -g tide_git_bg_color_urgent f38ba8
set -g tide_git_color 11111b
set -g tide_git_icon 
set -g tide_node_bg_color f9e2af
set -g tide_node_color 11111b
set -g tide_node_icon 
set -g tide_python_bg_color f9e2af
set -g tide_python_color 11111b
set -g tide_python_icon 
set -g tide_rustc_bg_color f9e2af
set -g tide_rustc_color 11111b
set -g tide_rustc_icon 
set -g tide_go_bg_color f9e2af
set -g tide_go_color 11111b
set -g tide_go_icon 
set -g tide_php_bg_color f9e2af
set -g tide_php_color 11111b
set -g tide_php_icon 
set -g tide_java_bg_color f9e2af
set -g tide_java_color 11111b
set -g tide_java_icon 
set -g tide_docker_bg_color eba0ac
set -g tide_docker_color 11111b
set -g tide_docker_icon 
set -g tide_character_color a6e3a1
set -g tide_character_color_failure f38ba8
set -g tide_character_icon ❯
# Default (non-vi) shells report an empty $fish_key_bindings, so Tide's
# character item falls through to the vi 'default' icon — point it at ❯ too.
set -g tide_character_vi_icon_default ❯
