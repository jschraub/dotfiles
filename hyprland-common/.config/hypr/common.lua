-- Shared Hyprland config for all machines (mini-mecha, oki-mecha).
-- Each machine's hyprland.lua does `require("common")` then layers on its
-- own deltas (GPU env vars, explicit monitor layout).
-- Resolution note: Hyprland prefixes ~/.config/hypr/ to require() paths, so
-- this and colors.lua resolve regardless of which stow package provides them.

local colors = require("colors")


------------------
---- MONITORS ----
------------------

-- Generic HDR default applied to ANY output. Machines with a known multi-head
-- layout (the laptop) override specific outputs on top of this in their own file.
hl.monitor({
    output        = "",
    mode          = "preferred",
    position      = "auto",
    scale         = 1,
    bitdepth      = 10,
    cm            = "hdr",
    sdrbrightness = 1.2,
    sdrsaturation = 1.2,
})


---------------------
---- MY PROGRAMS ----
---------------------

local terminal    = "ghostty"
local fileManager = "nautilus"
local menu        = "~/.local/bin/desktop-shell toggle launcher"
local browser     = "zen-browser"
local editor      = "~/.local/bin/desktop-editor"


-------------------
---- AUTOSTART ----
-------------------

-- Reconciles the internal panel against the real lid state.
-- See the script header for why lid binds cannot be
-- correct. Referenced from the binds, the monitor.added hook, and hypridle.
local lidDisplay = "~/.config/hypr/scripts/lid-display.sh"

hl.on("hyprland.start", function()
    hl.exec_cmd("~/.local/bin/desktop-polkit start")
    hl.exec_cmd("hyprctl setcursor Bibata-Modern-Amber 24")
    hl.exec_cmd("gnome-keyring-daemon --start --components=secrets,pkcs11")
    -- Keep idle/sleep evidence across reboots. Without systemd-cat, programs
    -- spawned here inherit /dev/null and their diagnostics are lost.
    hl.exec_cmd("systemd-cat --identifier=hypridle --level-prefix=false hypridle")
    hl.exec_cmd("sleep 1 && ~/.local/bin/desktop-shell start")
    -- After the compositor has settled: catches a session
    -- that started with the lid already shut, which fires no switch event. The
    -- delay must clear the script's own startup guard (see lid-display.sh).
    hl.exec_cmd("sleep 12 && " .. lidDisplay)
end)

-- An output appearing is the one moment we know the monitor set changed: re-apply
-- the lid rule (a resume can bring the panel back with the lid still shut) and
-- reconcile the panel. Atelier follows output changes without bar reloads.
--
-- These fire once per output during startup too. The script refuses to touch a
-- monitor in the session's first seconds, which matters: libaquamarine segfaults
-- when an output is disabled while the session is still coming up, and it takes
-- Hyprland down with it. hl.timer() would express the delay more directly but it
-- hangs config load, so the guard lives in the script.
hl.on("monitor.added", function()
    hl.exec_cmd(lidDisplay)
end)


-------------------------------
---- ENVIRONMENT VARIABLES ----
-------------------------------

hl.env("XCURSOR_THEME", "Bibata-Modern-Amber")
hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("EDITOR", (os.getenv("HOME") or "") .. "/.local/bin/desktop-editor --wait")
hl.env("VISUAL", (os.getenv("HOME") or "") .. "/.local/bin/desktop-editor --wait")


-----------------------
---- LOOK AND FEEL ----
-----------------------

hl.config({
    general = {
        gaps_in  = 2,
        gaps_out = 4,

        border_size = 2,

        col = {
            active_border = {
                colors = { "rgba(" .. colors.accent .. "ee)", "rgba(" .. colors.orange .. "ee)" },
                angle  = 45,
            },
            inactive_border = "rgba(" .. colors.line .. "aa)",
        },

        resize_on_border = false,
        allow_tearing    = false,

        layout = "dwindle",
    },

    cursor = {
        no_hardware_cursors = false,
    },

    decoration = {
        rounding       = 10,
        rounding_power = 2,

        active_opacity   = 1.0,
        inactive_opacity = 1.0,

        shadow = {
            enabled      = true,
            range        = 4,
            render_power = 3,
            color        = 0xee1a1a1a,
        },

        blur = {
            enabled  = true,
            size     = 3,
            passes   = 1,
            vibrancy = 0.1696,
        },
    },

    animations = {
        enabled = true,
    },

    dwindle = {
        preserve_split = true,
    },

    master = {
        new_status = "master",
    },

    misc = {
        force_default_wallpaper = 0,
        key_press_enables_dpms = true,
    },
})

-- Animation curves and leaves
hl.curve("easeOutQuint",   { type = "bezier", points = { {0.23, 1},    {0.32, 1} } })
hl.curve("easeInOutCubic", { type = "bezier", points = { {0.65, 0.05}, {0.36, 1} } })
hl.curve("linear",         { type = "bezier", points = { {0, 0},       {1, 1} } })
hl.curve("almostLinear",   { type = "bezier", points = { {0.5, 0.5},   {0.75, 1} } })
hl.curve("quick",          { type = "bezier", points = { {0.15, 0},    {0.1, 1} } })

hl.animation({ leaf = "global",        enabled = true, speed = 10,   bezier = "default" })
hl.animation({ leaf = "border",        enabled = true, speed = 5.39, bezier = "easeOutQuint" })
hl.animation({ leaf = "windows",       enabled = true, speed = 4.79, bezier = "easeOutQuint" })
hl.animation({ leaf = "windowsIn",     enabled = true, speed = 4.1,  bezier = "easeOutQuint", style = "popin 87%" })
hl.animation({ leaf = "windowsOut",    enabled = true, speed = 1.49, bezier = "linear",       style = "popin 87%" })
hl.animation({ leaf = "fadeIn",        enabled = true, speed = 1.73, bezier = "almostLinear" })
hl.animation({ leaf = "fadeOut",       enabled = true, speed = 1.46, bezier = "almostLinear" })
hl.animation({ leaf = "fade",          enabled = true, speed = 3.03, bezier = "quick" })
hl.animation({ leaf = "layers",        enabled = true, speed = 3.81, bezier = "easeOutQuint" })
hl.animation({ leaf = "layersIn",      enabled = true, speed = 4,    bezier = "easeOutQuint", style = "fade" })
hl.animation({ leaf = "layersOut",     enabled = true, speed = 1.5,  bezier = "linear",       style = "fade" })
hl.animation({ leaf = "fadeLayersIn",  enabled = true, speed = 1.79, bezier = "almostLinear" })
hl.animation({ leaf = "fadeLayersOut", enabled = true, speed = 1.39, bezier = "almostLinear" })
hl.animation({ leaf = "workspaces",    enabled = true, speed = 1.94, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "workspacesIn",  enabled = true, speed = 1.21, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "workspacesOut", enabled = true, speed = 1.94, bezier = "almostLinear", style = "fade" })
hl.animation({ leaf = "zoomFactor",    enabled = true, speed = 7,    bezier = "quick" })


---------------
---- INPUT ----
---------------

hl.config({
    input = {
        kb_layout  = "us",
        kb_variant = "",
        kb_model   = "",
        kb_options = "",
        kb_rules   = "",

        follow_mouse = 1,
        sensitivity  = 0,

        touchpad = {
            natural_scroll = false,
        },
    },
})

hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })


---------------------
---- KEYBINDINGS ----
---------------------

local mainMod = "SUPER"

-- Descriptions also populate the live, searchable Super+F1 shortcut panel.
hl.bind(mainMod .. " + F1", hl.dsp.exec_cmd("~/.local/bin/desktop-shell toggle bindings"), { description = "Show searchable Hyprland keybindings" })
hl.bind(mainMod .. " + return",    hl.dsp.exec_cmd(terminal), { description = "Open terminal (Ghostty)" })
hl.bind(mainMod .. " + Q",         hl.dsp.window.close(), { description = "Close active window" })
hl.bind(mainMod .. " + backspace", hl.dsp.exec_cmd(lidDisplay .. ' --all-on && sleep 0.5 && (command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown || hyprctl dispatch \'hl.dsp.exit()\')'), { description = "Exit Hyprland session" })
hl.bind(mainMod .. " + delete",    hl.dsp.exec_cmd("~/.local/bin/desktop-shell toggle power"), { description = "Open power menu (logout / reboot / shutdown)" })
hl.bind(mainMod .. " + E",         hl.dsp.exec_cmd(fileManager), { description = "Open file manager (Nautilus)" })
hl.bind(mainMod .. " + V", hl.dsp.exec_cmd("~/.local/bin/desktop-shell toggle clipboard"), { description = "Open clipboard history picker" })
hl.bind(mainMod .. " + SHIFT + space", hl.dsp.window.float({ action = "toggle" }), { description = "Toggle floating window" })
hl.bind(mainMod .. " + space",     hl.dsp.exec_cmd(menu), { description = "Open application launcher" })
hl.bind(mainMod .. " + P",         hl.dsp.window.pseudo(), { description = "Toggle pseudo tiling" })
hl.bind(mainMod .. " + J",         hl.dsp.layout("togglesplit"), { description = "Toggle tiling split direction" })
hl.bind(mainMod .. " + B",         hl.dsp.exec_cmd(browser), { description = "Open browser (Zen)" })
hl.bind(mainMod .. " + W",         hl.dsp.exec_cmd(editor), { description = "Open editor (Zed)" })
hl.bind(mainMod .. " + L",         hl.dsp.exec_cmd("~/.config/hypr/scripts/lock.sh"), { description = "Lock screen" })
hl.bind(mainMod .. " + G",         hl.dsp.exec_cmd("steam"), { description = "Open Steam" })
hl.bind(mainMod .. " + H",         hl.dsp.exec_cmd("lutris"), { description = "Open Lutris" })

-- Move focus with mainMod + arrow keys
hl.bind(mainMod .. " + left",  hl.dsp.focus({ direction = "left" }), { description = "Focus window to the left" })
hl.bind(mainMod .. " + right", hl.dsp.focus({ direction = "right" }), { description = "Focus window to the right" })
hl.bind(mainMod .. " + up",    hl.dsp.focus({ direction = "up" }), { description = "Focus window above" })
hl.bind(mainMod .. " + down",  hl.dsp.focus({ direction = "down" }), { description = "Focus window below" })

-- Rearrange tiled windows with mainMod + Shift + arrow keys
hl.bind(mainMod .. " + SHIFT + left",  hl.dsp.window.move({ direction = "left" }), { description = "Move tiled window left" })
hl.bind(mainMod .. " + SHIFT + right", hl.dsp.window.move({ direction = "right" }), { description = "Move tiled window right" })
hl.bind(mainMod .. " + SHIFT + up",    hl.dsp.window.move({ direction = "up" }), { description = "Move tiled window up" })
hl.bind(mainMod .. " + SHIFT + down",  hl.dsp.window.move({ direction = "down" }), { description = "Move tiled window down" })

-- Switch to / move active window to workspace [1-10]
for i = 1, 10 do
    local key = i % 10 -- 10 maps to key 0
    hl.bind(mainMod .. " + " .. key,         hl.dsp.focus({ workspace = i }), { description = "Switch to workspace " .. i })
    hl.bind(mainMod .. " + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }), { description = "Move window to workspace " .. i })
end

-- Special workspace (scratchpad)
hl.bind(mainMod .. " + S",         hl.dsp.workspace.toggle_special("magic"), { description = "Toggle scratchpad (special workspace)" })
hl.bind(mainMod .. " + SHIFT + S", hl.dsp.window.move({ workspace = "special:magic" }), { description = "Move window to scratchpad" })

-- Scroll through existing workspaces with mainMod + scroll
hl.bind(mainMod .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }), { description = "Switch to next workspace" })
hl.bind(mainMod .. " + mouse_up",   hl.dsp.focus({ workspace = "e-1" }), { description = "Switch to previous workspace" })

-- Move/resize windows with mainMod + LMB/RMB and dragging
hl.bind(mainMod .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true, description = "Move window by dragging" })
hl.bind(mainMod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true, description = "Resize window by dragging" })

-- Screenshots (grimblast via ~/.local/bin/screenshot.sh; copy to clipboard + save to ~/Pictures/Screenshots)
hl.bind("Print",               hl.dsp.exec_cmd("~/.local/bin/screenshot.sh area"), { description = "Screenshot selected region (save + clipboard)" })
hl.bind("SHIFT + Print",       hl.dsp.exec_cmd("~/.local/bin/screenshot.sh active"), { description = "Screenshot active window (save + clipboard)" })
hl.bind(mainMod .. " + Print", hl.dsp.exec_cmd("~/.local/bin/screenshot.sh output"), { description = "Screenshot focused monitor (save + clipboard)" })

-- Multimedia keys (locked = active even on lockscreen, repeating = key-repeat)
hl.bind("XF86AudioRaiseVolume",  hl.dsp.exec_cmd("~/.local/bin/desktop-control volume-up"),       { locked = true, repeating = true, description = "Raise volume 5%" })
hl.bind("XF86AudioLowerVolume",  hl.dsp.exec_cmd("~/.local/bin/desktop-control volume-down"),     { locked = true, repeating = true, description = "Lower volume 5%" })
hl.bind("XF86AudioMute",         hl.dsp.exec_cmd("~/.local/bin/desktop-control volume-mute"),     { locked = true, repeating = true, description = "Toggle speaker mute" })
hl.bind("XF86AudioMicMute",      hl.dsp.exec_cmd("~/.local/bin/desktop-control mic-mute"),        { locked = true, repeating = true, description = "Toggle microphone mute" })
hl.bind("XF86MonBrightnessUp",   hl.dsp.exec_cmd("~/.local/bin/desktop-control brightness-up"),   { locked = true, repeating = true, description = "Raise screen brightness 5%" })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("~/.local/bin/desktop-control brightness-down"), { locked = true, repeating = true, description = "Lower screen brightness 5%" })

-- playerctl media keys
hl.bind("XF86AudioNext",  hl.dsp.exec_cmd("playerctl next"),       { locked = true, description = "Next media track" })
hl.bind("XF86AudioPause", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true, description = "Play / pause media" })
hl.bind("XF86AudioPlay",  hl.dsp.exec_cmd("playerctl play-pause"), { locked = true, description = "Play / pause media" })
hl.bind("XF86AudioPrev",  hl.dsp.exec_cmd("playerctl previous"),   { locked = true, description = "Previous media track" })

-- Laptop lid. Both edges run the same reconcile against /proc/acpi/button/lid so
-- the binds and the resume path can never disagree about which one is authoritative.
-- No-op on machines without a lid.
hl.bind("switch:on:Lid Switch",  hl.dsp.exec_cmd(lidDisplay), { locked = true, description = "Reconcile displays when laptop lid closes" })
hl.bind("switch:off:Lid Switch", hl.dsp.exec_cmd(lidDisplay), { locked = true, description = "Reconcile displays when laptop lid opens" })


--------------------------------
---- WINDOWS AND WORKSPACES ----
--------------------------------

hl.window_rule({
    name           = "suppress-maximize-events",
    match          = { class = ".*" },
    suppress_event = "maximize",
})

hl.window_rule({
    name  = "fix-xwayland-drags",
    match = {
        class      = "^$",
        title      = "^$",
        xwayland   = true,
        float      = true,
        fullscreen = false,
        pin        = false,
    },
    no_focus = true,
})

hl.window_rule({
    name  = "move-hyprland-run",
    match = { class = "hyprland-run" },
    move  = "20 monitor_h-120",
    float = true,
})

hl.window_rule({
    name   = "nmtui_applet",
    match  = { title = "^(nmtui-float)$" },
    float  = true,
    size   = "700 500",
    center = true,
})

hl.window_rule({
    name   = "network-displays",
    match  = { title = "^(Network Displays)$" },
    float  = true,
    size   = "500 500",
    center = true,
})

hl.window_rule({
    name   = "screen-share",
    match  = { title = "^(Select what to share)$" },
    float  = true,
    size   = "400 300",
    center = true,
})
