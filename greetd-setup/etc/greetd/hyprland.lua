-- Minimal Hyprland config for greetd + ReGreet.
-- This runs the greeter and exits Hyprland when done.
-- Kept standalone (no require of the user's hyprland-common) because it runs
-- as the `greeter` user, which has no access to /home/jars/.config/hypr.

hl.on("hyprland.start", function()
    -- One command, in order: settle the displays, THEN run the greeter, THEN exit.
    -- These used to be two independent hl.exec_cmd calls, which race -- ReGreet can
    -- map its window before the panel is disabled.
    --
    -- Never light a shut laptop panel: with the lid closed and an external monitor
    -- attached, ReGreet's window lands on the internal display and the machine looks
    -- hung at a black screen. Guarded on an external head so a lid-closed boot with
    -- no external monitor still gets a greeter.
    --
    -- Inlined rather than shared with the user's scripts/lid-display.sh because this
    -- runs as `greeter`, which cannot read /home/jars -- see the header note. The
    -- files it does read (/proc/acpi/button/lid, /sys/class/drm) are world-readable.
    --
    -- No `set -e`: a greeter that fails to reach `regreet` is a machine nobody can
    -- log into. Every step here is best-effort.
    hl.exec_cmd([[
        set -u

        # At boot the DRM connector shows up in /sys well before the compositor has
        # a monitor for it. Disabling the panel in that window could leave zero
        # outputs, so wait (bounded) for Hyprland itself to report a non-internal
        # head before touching anything.
        external_up() {
            hyprctl monitors 2>/dev/null |
                sed -n 's/^Monitor \([^ ]*\) .*/\1/p' |
                grep -qv '^\(eDP\|LVDS\|DSI\)'
        }

        i=0
        while [ "$i" -lt 30 ] && ! external_up; do
            sleep 0.1
            i=$((i + 1))
        done

        if external_up && grep -qs closed /proc/acpi/button/lid/*/state; then
            for d in /sys/class/drm/card*-eDP-*/status; do
                [ -r "$d" ] || continue
                # Status, not just the glob: a hybrid-GPU laptop exposes an eDP
                # connector per card and only one of them is the real panel.
                [ "$(cat "$d")" = connected ] || continue
                c=${d%/status}; c=${c##*/}; c=${c#*-}
                hyprctl eval "hl.monitor({ output = \"$c\", disabled = true })" >/dev/null 2>&1
            done
        fi

        regreet

        # `hyprctl dispatch exit` is DEAD under the Lua parser: hyprctl evaluates its
        # argument as Lua and the bare identifier `exit` is nil there, so the greeter
        # never tore itself down when regreet finished. greetd then races the handoff
        # ("Failed to start session scope: Resource deadlock avoided"), the greeter
        # Hyprland aborts, and greetd gives up with "greeter exited without creating
        # a session" -- on screen, a login prompt that goes nowhere.
        hyprctl dispatch 'hl.dsp.exit()'
    ]])
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
