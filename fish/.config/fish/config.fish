source /usr/share/cachyos-fish-config/cachyos-config.fish

# Set up fzf key bindings
fzf --fish | source

# Set up starship prompt
eval "$(starship init fish)"

# overwrite greeting
# potentially disabling fastfetch
function fish_greeting
   # smth smth
end
fnm env --use-on-cd | source

# Claude Code OAuth token — pulled from GNOME Keyring (no plaintext on disk)
# Store with: secret-tool store --label="Claude Code OAuth" service claude-code key oauth_token
set -gx CLAUDE_CODE_OAUTH_TOKEN (secret-tool lookup service claude-code key oauth_token 2>/dev/null)

# GitHub PAT — pulled from GNOME Keyring (no plaintext on disk)
# Store with: secret-tool store --label="GitHub PAT" service github key pat
set -gx GH_TOKEN (secret-tool lookup service github key pat 2>/dev/null)
