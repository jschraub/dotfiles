-- Minimal Hyprland config for greetd + ReGreet.
-- This runs the greeter and exits Hyprland when done.
-- Kept standalone (no require of the user's hyprland-common) because it runs
-- as the `greeter` user, which has no access to /home/jars/.config/hypr.

hl.on("hyprland.start", function()
    hl.exec_cmd("regreet; hyprctl dispatch exit")
end)

hl.config({
    misc = {
        disable_hyprland_logo             = true,
        disable_splash_rendering          = true,
        disable_hyprland_guiutils_check   = true,
    },
})

-- Disable portal to prevent startup delays
hl.env("GTK_USE_PORTAL", "0")
hl.env("GDK_DEBUG", "no-portals")

-- NVIDIA support (matches the desktop config)
hl.env("LIBVA_DRIVER_NAME", "nvidia")
hl.env("GBM_BACKEND", "nvidia-drm")
hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")

-- Cursor theme
hl.env("XCURSOR_SIZE", "24")

-- Use all available monitors
hl.monitor({
    output   = "",
    mode     = "preferred",
    position = "auto",
    scale    = 1,
})
