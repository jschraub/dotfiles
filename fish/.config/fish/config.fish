# CachyOS fish base (interactive abbreviations, theme, etc.)
status is-interactive && source /usr/share/cachyos-fish-config/cachyos-config.fish

# Login shell is bash (so VS Code Remote-SSH's POSIX bootstrap works); bash execs
# fish for interactive sessions. Point $SHELL back at fish so tools that spawn
# $SHELL get fish. Exported, so child processes inherit it.
set -gx SHELL (command -v fish)

# Empty greeting
function fish_greeting
end

# Interactive-only setup. Kept out of non-interactive shells so Tide's prompt
# subshell (a `fish -c`, which re-sources this file) stays fast — otherwise these
# (notably the secret-tool keyring lookups, ~70ms) would run on every prompt.
# Exported vars set here are inherited by that subshell, so nothing is lost.
if status is-interactive
    # fzf key bindings
    fzf --fish | source

    # Prompt: Tide (installed via fisher; themed in conf.d/tide_theme.fish to
    # mirror the Claude Code statusline). On a new machine `fisher update` reads
    # ../fish_plugins and installs it; if it doesn't pick Tide up, run:
    #   fisher install ilancosman/tide@v6
    # To revert to starship, uncomment:
    # eval "$(starship init fish)"

    # node version manager (adds a cd hook)
    fnm env --use-on-cd | source

    # Secrets from GNOME Keyring — no plaintext on disk.
    # Store with: secret-tool store --label="Claude Code OAuth" service claude-code key oauth_token
    set -gx CLAUDE_CODE_OAUTH_TOKEN (secret-tool lookup service claude-code key oauth_token 2>/dev/null)
    # Store with: secret-tool store --label="GitHub PAT" service github key pat
    set -gx GH_TOKEN (secret-tool lookup service github key pat 2>/dev/null)
end
