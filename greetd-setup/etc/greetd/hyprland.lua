-- Minimal Hyprland config for greetd + ReGreet.
-- This runs the greeter and exits Hyprland when done.
-- Kept standalone (no require of the user's hyprland-common) because it runs
-- as the `greeter` user, which has no access to /home/jars/.config/hypr.

hl.on("hyprland.start", function()
    -- Never light a shut laptop panel. The greeter has no lid handling of its own,
    -- so with the lid closed and an external monitor attached ReGreet's window can
    -- land on the internal display and the machine looks hung at a black screen.
    -- Guarded on an external head being present, so a lid-closed boot with no
    -- external monitor still gets a greeter. Inlined rather than shared with the
    -- user's scripts/lid-display.sh because this runs as `greeter`, which cannot
    -- read /home/jars -- see the header note.
    hl.exec_cmd([[
        set -eu
        externals=0
        for s in /sys/class/drm/card*-*/status; do
            [ -r "$s" ] || continue
            c=${s%/status}; c=${c##*/}; c=${c#*-}
            case "$c" in eDP*|LVDS*|DSI*|Writeback*) continue ;; esac
            [ "$(cat "$s")" = connected ] && externals=$((externals + 1)) || true
        done
        if [ "$externals" -gt 0 ] && grep -qs closed /proc/acpi/button/lid/*/state; then
            for d in /sys/class/drm/card*-eDP-*/status; do
                [ -r "$d" ] || continue
                # Status, not just the glob: a hybrid-GPU laptop exposes an eDP
                # connector per card and only one of them is the real panel.
                [ "$(cat "$d")" = connected ] || continue
                c=${d%/status}; c=${c##*/}; c=${c#*-}
                hyprctl eval "hl.monitor({ output = \"$c\", disabled = true })" >/dev/null 2>&1 || true
            done
        fi
    ]])
    -- `hyprctl dispatch exit` is DEAD under the Lua parser: hyprctl evaluates the
    -- argument as Lua, and the bare identifier `exit` is nil there, so the greeter
    -- never tore itself down when regreet finished. greetd then races the handoff
    -- ("Failed to start session scope: Resource deadlock avoided"), the greeter
    -- Hyprland aborts, and greetd gives up with "greeter exited without creating a
    -- session" -- which on screen is a login prompt that never goes anywhere.
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
