#!/usr/bin/env fish
# Copy to ~/.config/upall/custom.fish and add machine-local updater commands.
if not test -f "$HOME/Games/AsheronsCall/.ac-jars-root.json"
    echo "AC:Unreal is not installed here; skipping."
else if pgrep -x ACUnreal >/dev/null
    echo "AC:Unreal is running; skipping its update."
else
    bash "$HOME/code/ac-jars/install.sh" update --yes --no-shortcut
end
