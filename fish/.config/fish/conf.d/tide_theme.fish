# Tide theme — mirrors the Claude Code statusline (Catppuccin Mocha powerline).
# Stow-managed: edit here, then bump the version number below to re-apply.
# Segments: user → clock → pwd → git → languages → docker (empty ones auto-hidden).

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

if test "$_tide_theme_version" != 3
    set -U tide_left_prompt_items user clock pwd git node python rustc go php java docker newline character
    set -e tide_right_prompt_items # empty list (no right prompt); '' would be one empty item
    set -U tide_left_prompt_prefix 
    set -U tide_left_prompt_suffix 
    set -U tide_left_prompt_separator_diff_color 
    set -U tide_left_prompt_separator_same_color ''
    set -U tide_right_prompt_prefix ''
    set -U tide_right_prompt_suffix ''
    set -U tide_right_prompt_separator_diff_color 
    set -U tide_right_prompt_separator_same_color ''
    set -U tide_prompt_pad_items true
    set -U tide_prompt_add_newline_before true
    set -U tide_prompt_transient_enabled false
    set -U tide_user_bg_color cba6f7
    set -U tide_user_color 11111b
    set -U tide_user_icon 
    set -U tide_clock_bg_color 89b4fa
    set -U tide_clock_color 11111b
    set -U tide_clock_icon 
    set -U tide_clock_format %H:%M
    set -U tide_pwd_bg_color 74c7ec
    set -U tide_pwd_color_dirs 11111b
    set -U tide_pwd_color_anchors 11111b
    set -U tide_pwd_color_truncated_dirs 11111b
    set -U tide_pwd_icon 
    set -U tide_pwd_icon_home 
    set -U tide_pwd_icon_unwritable 
    set -U tide_git_bg_color a6e3a1
    set -U tide_git_bg_color_unstable fab387
    set -U tide_git_bg_color_urgent f38ba8
    set -U tide_git_color 11111b
    set -U tide_git_icon 
    set -U tide_node_bg_color f9e2af
    set -U tide_node_color 11111b
    set -U tide_node_icon 
    set -U tide_python_bg_color f9e2af
    set -U tide_python_color 11111b
    set -U tide_python_icon 
    set -U tide_rustc_bg_color f9e2af
    set -U tide_rustc_color 11111b
    set -U tide_rustc_icon 
    set -U tide_go_bg_color f9e2af
    set -U tide_go_color 11111b
    set -U tide_go_icon 
    set -U tide_php_bg_color f9e2af
    set -U tide_php_color 11111b
    set -U tide_php_icon 
    set -U tide_java_bg_color f9e2af
    set -U tide_java_color 11111b
    set -U tide_java_icon 
    set -U tide_docker_bg_color eba0ac
    set -U tide_docker_color 11111b
    set -U tide_docker_icon 
    set -U tide_character_color a6e3a1
    set -U tide_character_color_failure f38ba8
    set -U tide_character_icon ❯
    # Default (non-vi) shells report an empty $fish_key_bindings, so Tide's
    # character item falls through to the vi 'default' icon — point it at ❯ too.
    set -U tide_character_vi_icon_default ❯
    set -U _tide_theme_version 3
end
