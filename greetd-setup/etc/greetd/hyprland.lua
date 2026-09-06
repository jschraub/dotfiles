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

-- Use all available monitors, pinned to SDR.
--
-- cm is set explicitly because render:cm_auto_hdr defaults to 1, so an unpinned
-- output has its colour mode chosen by auto-detection -- on an HDR-capable panel
-- the greeter could come up in HDR mode. That is worth avoiding on both counts:
--
--  * It buys nothing. ReGreet is a GTK app and renders SDR content regardless.
--  * A monitor in HDR mode showing SDR content that is treated as sRGB looks
--    blown out and oversaturated. The session compensates with sdrbrightness /
--    sdrsaturation (see hyprland-common/common.lua); the greeter does not, so
--    letting it drift into HDR is how you get a washed-out login screen.
--
-- The session still runs the external head at bitdepth 10 / cm hdr, so logging
-- out retrains the link SDR<->HDR. That costs a blank-and-resync on the Ark and
-- is the accepted trade for a greeter that always looks right.
hl.monitor({
    output   = "",
    mode     = "preferred",
    position = "auto",
    scale    = 1,
    cm       = "srgb",
})


-- Keep the greeter off a shut laptop panel.
--
-- Hyprland puts the first monitor's workspace up first, so with the lid closed
-- ReGreet lands on the internal panel and the machine looks hung -- you have to
-- open the lid to log in.
--
-- CRITICAL: this is decided at CONFIG LOAD and expressed as `disabled` in the
-- initial monitor rule, so Hyprland never brings the panel up at all. Do NOT
-- reimplement this as a runtime `hyprctl` disable from hyprland.start. That was
-- tried and it made the machine unbootable: libaquamarine segfaults when a LIVE
-- output is torn down (Aquamarine::SDRMConnector::disconnect inside
-- ~CDRMBackend), which killed the compositor under regreet, so regreet exited
-- without creating a session and greetd restarted it -- a loop whose every
-- iteration was a modeset, seen on the external monitor as signal dropping and
-- returning. Never enabling the output avoids that path entirely.
--
-- Gated on BOTH the lid being shut and an external head being present, so the
-- greeter can never end up with no display you can actually look at:
--   lid open           -> panel stays, greeter is visible on it
--   no external        -> panel stays, laptop-only boots still work
--   lid shut + external -> panel off, greeter goes to the external
--
-- Runs as `greeter`, which cannot read /home/jars, so this is standalone rather
-- than sharing hyprland-common's scripts/lid-display.sh. Both files it reads are
-- world-readable.

local function read_file(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local contents = f:read("*a")
    f:close()
    return contents
end

local function lid_closed()
    -- Lua has no globbing and the ACPI button name is not fixed (LID0 here).
    local pipe = io.popen("cat /proc/acpi/button/lid/*/state 2>/dev/null")
    if not pipe then return false end
    local state = pipe:read("*a") or ""
    pipe:close()
    return state:find("closed") ~= nil
end

local internal_panels, external_count = {}, 0

local drm = io.popen("ls -1 /sys/class/drm 2>/dev/null")
if drm then
    for entry in drm:lines() do
        -- card2-eDP-2 -> eDP-2. Bare "card2" and renderD* do not match.
        local name = entry:match("^card%d+%-(.+)$")
        if name and not name:match("^Writeback") then
            local status = read_file("/sys/class/drm/" .. entry .. "/status")
            -- Anchored: "disconnected" must not match.
            if status and status:find("^connected") then
                if name:match("^eDP") or name:match("^LVDS") or name:match("^DSI") then
                    -- A hybrid-GPU laptop exposes an eDP connector per card and
                    -- only the connected one is the real panel; the status check
                    -- above has already filtered the phantom.
                    internal_panels[#internal_panels + 1] = name
                else
                    external_count = external_count + 1
                end
            end
        end
    end
    drm:close()
end

if external_count > 0 and lid_closed() then
    for _, panel in ipairs(internal_panels) do
        hl.monitor({ output = panel, disabled = true })
    end
end
