-- oki-mecha
-- Shared config lives in common.lua; this file layers on machine-specific deltas.
--
-- oki-mecha currently has NO deltas: the generic HDR monitor catch-all in
-- common.lua covers its display, and it needs no GPU-specific env vars.
-- Add machine-specific monitors / env below if that changes.
--
-- NOTE: written on mini-mecha and not yet tested on oki-mecha hardware.

-- require() resolves relative to this file's real (symlink-resolved) path, which
-- under GNU stow is this machine's package dir -- NOT where common.lua/colors.lua
-- live. Prepend the actual config dir so require() finds the stow-linked modules.
package.path = (os.getenv("HOME") or "") .. "/.config/hypr/?.lua;" .. package.path

require("common")
