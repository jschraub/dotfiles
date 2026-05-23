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
