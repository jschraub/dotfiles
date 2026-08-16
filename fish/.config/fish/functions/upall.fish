function upall --description 'Update Arch packages via paru and Flatpaks, then refresh Cachy-Update'
    echo "Starting system and AUR updates..."
    paru -Syu --noconfirm

    echo "---"

    echo "Starting Flatpak updates..."
    flatpak update -y

    echo "---"

    # paru/flatpak don't touch cachy-update's cached state, so its tray icon and
    # notification keep advertising the pre-update list until the daily timer
    # fires. Re-check here to clear it immediately.
    echo "Refreshing Cachy-Update status..."
    arch-update --check

    echo "---"
    echo "All updates complete!"
end
