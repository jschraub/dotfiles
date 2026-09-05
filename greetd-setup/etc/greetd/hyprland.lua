-- Minimal Hyprland config for greetd + ReGreet.
-- This runs the greeter and exits Hyprland when done.
-- Kept standalone (no require of the user's hyprland-common) because it runs
-- as the `greeter` user, which has no access to /home/jars/.config/hypr.

hl.on("hyprland.start", function()
    -- NO monitor/lid handling here, deliberately. An earlier version disabled the
    -- internal panel when the lid was shut so ReGreet could not land on a display
    -- nobody can see. It made the machine unbootable: libaquamarine segfaults when
    -- a monitor is disabled while the greeter is still coming up, Hyprland dies,
    -- regreet loses its Wayland display mid-init and exits without creating a
    -- session, and greetd restarts it -- a loop whose every iteration is a modeset,
    -- which on the external monitor reads as signal dropping and returning. It
    -- raced regreet's startup, so it only bit some of the time. The greeter's own
    -- log ends at "Cancelling greetd session" with nothing after it.
    --
    -- The problem that guard was written for turned out to be the hyprlock PAM
    -- stack instead (see pam-setup/etc/pam.d/hyprlock), which is fixed. Do not
    -- reintroduce monitor changes here without a way to test a real boot.
    --
    -- `hyprctl dispatch exit` is DEAD under the Lua parser: hyprctl evaluates its
    -- argument as Lua and the bare identifier `exit` is nil there, so the greeter
    -- never tore itself down when regreet finished.
    hl.exec_cmd("regreet; hyprctl dispatch 'hl.dsp.exit()'")
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
