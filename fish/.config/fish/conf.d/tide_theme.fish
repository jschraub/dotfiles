# Tide theme - Atelier Amber powerline.
# Stow-managed and fully declarative: palette in 00-atelier-palette.fish,
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

# Custom git item: branch + dirty '*', graphite→dark amber bg
# (overrides Tide's built-in, which forces white branch text).
function _tide_item_git
    set -l branch (git branch --show-current 2>/dev/null)
    or return
    test -z "$branch"; and return
    set -l changes (git --no-optional-locks status --porcelain 2>/dev/null)
    if test (count $changes) -gt 0
        set -g tide_git_bg_color $tide_git_bg_color_unstable
        set -g tide_git_color $atelier_text
        _tide_print_item git $tide_git_icon' ' $branch ' *'
    else
        set -g tide_git_bg_color $atelier_prompt_git_bg
        set -g tide_git_color $atelier_accent
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
# Four ordered gray roles; all language/environment items share the final shade.
set -g tide_user_bg_color $atelier_prompt_user_bg
set -g tide_user_color $atelier_accent
set -g tide_user_icon 
set -g tide_clock_bg_color $atelier_prompt_clock_bg
set -g tide_clock_color $atelier_accent
set -g tide_clock_icon 
set -g tide_clock_format %H:%M
set -g tide_pwd_bg_color $atelier_accent
set -g tide_pwd_color_dirs $atelier_onAccent
set -g tide_pwd_color_anchors $atelier_onAccent
set -g tide_pwd_color_truncated_dirs $atelier_onAccent
set -g tide_pwd_icon 
set -g tide_pwd_icon_home 
set -g tide_pwd_icon_unwritable 
set -g tide_git_bg_color $atelier_prompt_git_bg
set -g tide_git_bg_color_unstable $atelier_selection
set -g tide_git_bg_color_urgent $atelier_danger
set -g tide_git_color $atelier_accent
set -g tide_git_icon 
set -g tide_node_bg_color $atelier_prompt_environment_bg
set -g tide_node_color $atelier_accent
set -g tide_node_icon 
set -g tide_python_bg_color $atelier_prompt_environment_bg
set -g tide_python_color $atelier_accent
set -g tide_python_icon 
set -g tide_rustc_bg_color $atelier_prompt_environment_bg
set -g tide_rustc_color $atelier_accent
set -g tide_rustc_icon 
set -g tide_go_bg_color $atelier_prompt_environment_bg
set -g tide_go_color $atelier_accent
set -g tide_go_icon 
set -g tide_php_bg_color $atelier_prompt_environment_bg
set -g tide_php_color $atelier_accent
set -g tide_php_icon 
set -g tide_java_bg_color $atelier_prompt_environment_bg
set -g tide_java_color $atelier_accent
set -g tide_java_icon 
set -g tide_docker_bg_color $atelier_prompt_environment_bg
set -g tide_docker_color $atelier_accent
set -g tide_docker_icon 
set -g tide_character_color $atelier_accent
set -g tide_character_color_failure $atelier_danger
set -g tide_character_icon ❯
# Default (non-vi) shells report an empty $fish_key_bindings, so Tide's
# character item falls through to the vi 'default' icon — point it at ❯ too.
set -g tide_character_vi_icon_default ❯
