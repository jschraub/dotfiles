function upall --description 'Update Arch packages via yay and Flatpaks'
    echo "Starting system and AUR updates..."
    yay -Syu --noconfirm
    
    echo "---"
    
    echo "Starting Flatpak updates..."
    flatpak update -y
    
    echo "---"
    echo "All updates complete!"
end
