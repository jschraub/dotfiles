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
    -- TEMPORARY DIAGNOSTIC -- remove once the lid-closed greeter is understood.
    -- The greeter's own Hyprland log lives in /run/user/952 and is destroyed when
    -- the greeter exits, so there is no way to see what it did with the monitors
    -- after the fact. Copy the evidence somewhere that survives. Backgrounded and
    -- entirely best-effort: it must never be able to stop regreet from running.
    hl.exec_cmd([[
        (
            sleep 4
            echo "=== monitors all ==="; hyprctl monitors all
            echo "=== layers ===";       hyprctl layers
            echo "=== clients ===";      hyprctl clients
            echo "=== lid ===";          cat /proc/acpi/button/lid/*/state
            echo "=== drm ==="
            for f in /sys/class/drm/card*-*/status; do echo "$f $(cat "$f")"; done
            sleep 2
            echo "=== hyprland.log ==="
            cat "$XDG_RUNTIME_DIR"/hypr/*/hyprland.log
        ) > /tmp/greeter-diag.txt 2>&1
        chmod 644 /tmp/greeter-diag.txt
    ]])

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

local internal_panels, externals = {}, {}

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
                    -- First line of `modes` is the connector's preferred
                    -- RESOLUTION (no refresh rate). Used below to pin a
                    -- conservative mode; nil is fine, it just means no pin.
                    local modes = read_file("/sys/class/drm/" .. entry .. "/modes")
                    externals[#externals + 1] = {
                        name = name,
                        res  = modes and modes:match("^(%d+x%d+)"),
                    }
                end
            end
        end
    end
    drm:close()
end

-- Pin every external head to its native resolution at 120Hz.
--
-- `mode = "preferred"` takes the connector's FIRST advertised mode, which on the
-- Odyssey Ark is 3840x2160@164.99Hz. The greeter modeset that rate, logged
-- "drm: Cannot commit when a page-flip is awaiting" twice, and put nothing on
-- screen -- the login screen was genuinely there (regreet mapped, visible and
-- focused, internal panel correctly disabled) but the monitor showed nothing.
-- The session has always pinned 120Hz, which is why it never hit this.
--
-- 120 matches the session, so logging in no longer changes the refresh rate --
-- one less link retrain, and one less chance for the Ark to drop and re-acquire
-- signal. It is a deliberate trade against 60, which is the rate every display
-- supports at its native resolution: 120 is verified on THIS monitor and this
-- machine never drives another one.
--
-- Safe against a display that cannot do 120: Hyprland honours a requested mode
-- rather than falling back to `preferred`, verified by asking DP-5 for an
-- unadvertised 144Hz and getting 3840x2160@144. So a bad pin can never silently
-- land back on the 165Hz mode that started this. If a future monitor shows
-- nothing at the greeter, drop this to @60 -- reachable from a TTY on Ctrl+Alt+F2
-- since greetd holds VT1.
local EXTERNAL_REFRESH = "120"

for _, ext in ipairs(externals) do
    if ext.res then
        hl.monitor({ output = ext.name, mode = ext.res .. "@" .. EXTERNAL_REFRESH })
    end
end

if #externals > 0 and lid_closed() then
    for _, panel in ipairs(internal_panels) do
        hl.monitor({ output = panel, disabled = true })
    end
end
