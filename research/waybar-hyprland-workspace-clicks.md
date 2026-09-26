# Waybar `hyprland/workspaces` Clicks

## Finding

Yes. Upstream reports confirm non-working workspace clicks, including an exact
Waybar `v0.15.0` + Hyprland `0.56.2` report. The strongest evidence points to
an IPC dispatch-protocol mismatch:

- Waybar issue [#5294](https://github.com/Alexays/Waybar/issues/5294) reports
  that exact version pair and says `hyprland/workspaces` clicks do nothing
  under a Lua Hyprland configuration.
- Waybar `0.15.0`'s tagged workspace click handler sends legacy commands such
  as `dispatch workspace 2` directly.[Waybar source](https://raw.githubusercontent.com/Alexays/Waybar/0.15.0/src/modules/hyprland/workspace.cpp)
- Hyprland `v0.56.2` evaluates `dispatch` through `hl.dispatch(...)` when the
  Lua manager is active, while the legacy manager resolves a textual
  dispatcher.[Hyprland source](https://raw.githubusercontent.com/hyprwm/Hyprland/v0.56.2/src/debug/HyprCtl.cpp)
  Thus, `Waybar 0.15.0 + Hyprland 0.56.2 + Lua config` is a reproducible
  incompatible combination.

## Configuration Cause

Hyprland configuration naming can select the failing protocol. In `v0.56.2`,
Hyprland selects the Lua manager only when the main config path has a `.lua`
extension; otherwise it selects the legacy manager, whose reported name is
`hyprlang`.[Hyprland source](https://raw.githubusercontent.com/hyprwm/Hyprland/v0.56.2/src/config/ConfigManager.cpp)
The same build exposes the active manager as `configProvider: lua` or
`configProvider: hyprlang` in `hyprctl systeminfo`.[Hyprland source](https://raw.githubusercontent.com/hyprwm/Hyprland/v0.56.2/src/helpers/SystemInfo.cpp)

This creates two opposite failure modes:

- Waybar `0.15.0` with `configProvider: lua`: Waybar lacks the Lua dispatch
  adaptation and sends legacy syntax; this is the exact #5294 case.[Waybar source](https://raw.githubusercontent.com/Alexays/Waybar/0.15.0/src/modules/hyprland/workspace.cpp)
  [Waybar PR #5013](https://github.com/Alexays/Waybar/pull/5013)
- Waybar containing PR #5013 but Hyprland `0.55+` with a traditional
  `hyprland.conf`: the old version-based detection can select Lua syntax for
  a legacy Hyprland instance; Waybar issue [#5198](https://github.com/Alexays/Waybar/issues/5198)
  documents the unclickable buttons and PR [#5231](https://github.com/Alexays/Waybar/pull/5231)
  identifies and fixes that mismatch.

Therefore configuration can cause the symptom, specifically by selecting a
Hyprland config manager that does not match the Waybar build's dispatch
behavior. The Hyprland version alone is not sufficient to diagnose it.[Waybar PR #5231](https://github.com/Alexays/Waybar/pull/5231)

The `hyprland/workspaces` module does not define an `on-click` setting in the
Waybar `0.15.0` man page; its buttons are wired to switch workspaces by the
module itself.[Waybar man page](https://raw.githubusercontent.com/Alexays/Waybar/0.15.0/man/waybar-hyprland-workspaces.5.scd)
The generic `ext/workspaces` module is different and does define
`on-click: activate`.[Waybar workspace documentation](https://github.com/Alexays/Waybar/wiki/Module:-Workspaces)
Adding `on-click` to `hyprland/workspaces` is therefore not the fix for this
IPC mismatch.

## Confirmed Fixes

- For Lua-config Hyprland, use a Waybar build containing merged PR [#5013](https://github.com/Alexays/Waybar/pull/5013), which changes workspace dispatches to the Lua `hl.dsp` API. The published `0.15.0` release predates that PR: the release is dated February 6, 2026, while PR #5013 merged May 4, 2026.[Waybar release 0.15.0](https://github.com/Alexays/Waybar/releases/tag/0.15.0)
- For a traditional `hyprland.conf` on Hyprland `0.55+`, use a Waybar build containing merged PR [#5231](https://github.com/Alexays/Waybar/pull/5231), which detects `configProvider` from read-only `systeminfo` instead of assuming the protocol from the Hyprland version.
- Before changing anything, compare `hyprctl systeminfo`'s `configProvider` with the Waybar build: `lua` requires Lua-dispatch support; `hyprlang` requires legacy dispatch selection.[Hyprland source](https://raw.githubusercontent.com/hyprwm/Hyprland/v0.56.2/src/helpers/SystemInfo.cpp)

The `ext/workspaces` substitution is only a community-reported workaround,
not a confirmed equivalent replacement: one upstream issue comment reports it
working, while another reports that it did not work for that setup.[Waybar issue comment](https://github.com/Alexays/Waybar/issues/5198#issuecomment-4954418150)
[Contrary report](https://github.com/Alexays/Waybar/issues/5198#issuecomment-5039662977)
