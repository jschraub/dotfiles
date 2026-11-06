-- oki-mecha
-- Shared config lives in common.lua; this file layers on machine-specific deltas.
--
-- The generic HDR monitor catch-all in common.lua covers its display.
-- Its wallpaper is separate from mini-mecha; no GPU-specific env vars needed.

-- require() resolves relative to this file's real (symlink-resolved) path, which
-- under GNU stow is this machine's package dir -- NOT where common.lua/colors.lua
-- live. Prepend the actual config dir so require() finds the stow-linked modules.
package.path = (os.getenv("HOME") or "") .. "/.config/hypr/?.lua;" .. package.path

require("common")

hl.env("ATELIER_WALLPAPER_CONFIG", (os.getenv("HOME") or "") .. "/.config/hypr/hyprpaper-oki-mecha.conf")
