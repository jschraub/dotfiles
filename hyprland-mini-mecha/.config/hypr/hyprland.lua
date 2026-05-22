-- mini-mecha (laptop: NVIDIA RTX 5070 Mobile + AMD Radeon 890M)
-- Shared config lives in common.lua; this file layers on machine-specific deltas.

-- require() resolves relative to this file's real (symlink-resolved) path, which
-- under GNU stow is this machine's package dir -- NOT where common.lua/colors.lua
-- live. Prepend the actual config dir so require() finds the stow-linked modules.
package.path = (os.getenv("HOME") or "") .. "/.config/hypr/?.lua;" .. package.path

require("common")


-------------------------------
---- ENVIRONMENT VARIABLES ----
-------------------------------

-- Hybrid GPU: prefer the AMD card (card2) over NVIDIA (card1) as primary.
hl.env("AQ_DRM_DEVICES", "/dev/dri/card2:/dev/dri/card1")
hl.env("LIBVA_DRIVER_NAME", "nvidia")
hl.env("XDG_SESSION_TYPE", "wayland")
hl.env("GBM_BACKEND", "nvidia-drm")
hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")


------------------
---- MONITORS ----
------------------

-- Internal panel, left.
hl.monitor({
    output        = "eDP-2",
    mode          = "2560x1600@165",
    position      = "0x0",
    scale         = 1,
    bitdepth      = 10,
    cm            = "hdr",
    sdrbrightness = 1.2,
    sdrsaturation = 1.2,
})

-- External displays (one connected at a time), placed to the right of the panel.
for _, output in ipairs({
    { name = "DP-1", mode = "3840x2160@60" },
    { name = "DP-4", mode = "3840x2160@120" },
    { name = "DP-5", mode = "3840x2160@120" },
}) do
    hl.monitor({
        output        = output.name,
        mode          = output.mode,
        position      = "2560x0",
        scale         = 1,
        bitdepth      = 10,
        cm            = "hdr",
        sdrbrightness = 1.2,
        sdrsaturation = 1.2,
    })
end
