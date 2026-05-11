function upall --description 'Update Arch packages via paru and Flatpaks'
    echo "Starting system and AUR updates..."
    paru -Syu --noconfirm
    
    echo "---"
    
    echo "Starting Flatpak updates..."
    flatpak update -y
    
    echo "---"
    echo "All updates complete!"
end
