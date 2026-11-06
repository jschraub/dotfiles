# Quickshell migration scope audit

Date: 2026-11-06. Baseline: the current working checkout, including uncommitted
keybinding/menu changes. This is an audit and migration recommendation, not an
implementation. No desktop processes, installed packages, authentication policies,
or setup scripts were changed.

## Bottom line

Quickshell can consolidate the desktop **presentation layer**: application launcher,
keybinding browser, bar, power menu, calendar/audio panels, network picker, and
notification UI. It is a toolkit: installing it alone supplies none of our finished
menus. We must implement these in QML or adopt and customize an existing shell.

Keep Hyprland, Hypridle, Hyprlock, authentication, networking, sound, Bluetooth,
screen capture, and login/session infrastructure initially. Wallpaper rendering
and authentication prompts are optional later consolidation projects, not required
to solve the menu problem.

Upstream capability evidence and limitations are collected separately in
[quickshell-capabilities.md](quickshell-capabilities.md). Repository links below
are the evidence for what this setup actually uses.

## Live machine checks

Read-only checks ran on **oki-mecha**. Its active `~/.config/hypr/hyprland.lua`
resolves to the oki-mecha profile in this checkout. Shared Hyprland configuration,
Waybar, Wofi, SwayNC, wlogout, and Fuzzel network configuration resolve to this
checkout too. mini-mecha's profile was inspected on disk, not tested on hardware.

- Quickshell is not installed under the `quickshell` package name, and neither
  `qs` nor `quickshell` is on PATH.
- Waybar, SwayNC, Hyprpaper, Hypridle, polkit-gnome, gnome-keyring, PipeWire, and
  WirePlumber were running. Hyprland reported no config errors.
- NetworkManager, Bluetooth, UPower, power-profiles-daemon, and greetd were active.
  UPower/power-profiles-daemon being active does not mean this repo provisions
  them; they are not declared in its main desktop package registry.
- The selected installation drift audit returned **172 OK, 1 DRIFT, 1 UNKNOWN**:
  `PYTHONDONTWRITEBYTECODE=1 ./check-setup.sh hyprland waybar wofi wlogout greetd pam nautilus`.
- Drift: installed Waybar is **0.15.0-3.1**, below the checkout's required stable
  **0.16.0**; `waybar-git` is absent. This is an existing mismatch, not caused by
  Quickshell. No upgrade was attempted.
- Unknown: `/etc/greetd/config.toml` is not readable as this user. Other selected
  comparisons passed; no sudo or elevated inspection was attempted.

The drift checker checks declared files/packages, not full behavioral correctness.
See [SETUP-AUDIT.md](../SETUP-AUDIT.md). This audit does not claim hardware,
fingerprint, suspend/resume, or replacement-shell acceptance testing.

## Replacement inventory

| Current component | Current responsibility | Recommendation |
| --- | --- | --- |
| Wofi | Super+Space application launcher; Super+F1 shortcut reference | Replace both with Quickshell panels. Real headers, layouts, and independent padding should replace text/markup tricks. |
| Waybar | Top bar: workspaces, active window title, cast/VPN/network/Bluetooth/audio, keep-awake, battery, notifications, clock, power | Replace the whole visual bar, preserving its actions and state semantics. |
| `waybar-popup.py` + `popup.css` | Click-open calendar and default-output volume slider/mute | Replace with native Quickshell popups; preserve Escape/outside-click dismissal and correct output placement. |
| Fuzzel + `network-menu.sh` + `network.ini` | Wi-Fi selection, password prompt, rescan/radio, captive portal, VPN app entry, advanced network settings | Replace the UI. Port the existing connection policies rather than only drawing a new SSID list. Keep NetworkManager. |
| wlogout + `wlogout-centered.sh` | Centered lock/logout/shutdown/reboot grid; Super+Delete and bar button | Replace with a matching power panel. Continue calling the existing lock wrapper and system/session commands. |
| SwayNC | Notification server, toast rendering, notification center, DND | Good candidate for a later migration stage. Quickshell must implement both notification handling and presentation, not merely display an icon. |
| `vpn-status.sh` | NetworkManager VPN state formatted as Waybar JSON/Pango | Replace the presentation adapter; reuse state logic initially if useful. Preserve Proton's ownership of its VPN. |
| `keep-awake.sh` | Session-scoped logind idle inhibitor, plus Waybar-shaped status | **Keep the inhibitor backend**, relocate outside the retiring Waybar Stow package, and replace only its presentation adapter. |
| Hyprpaper | Mordor desktop wallpaper, cover fit | Optional later replacement with a Quickshell background surface; not needed for bar/menu migration. Keep assets. |
| Hyprlock + `lock.sh` | Secure lock screen, password PAM, optional native fingerprint detection | **Keep initially.** A Quickshell lock screen is a separate security-sensitive project, not a cosmetic popup replacement. |
| Hypridle | Dim/lock/display-off/suspend timings and suspend/resume hooks | **Keep.** It controls lifecycle and inhibition, not just visual UI. |
| polkit-gnome | Privilege authentication prompts | Optional later UI replacement only if a proper polkit agent is implemented; keep for the initial migration. |
| Blueman | Full Bluetooth manager launched by the bar | Keep as an advanced-settings fallback. A Quickshell device picker can later cover common operations; BlueZ stays. |
| pavucontrol | Devices, inputs, per-application routing/levels | Keep as an advanced-settings fallback. A volume slider alone does not replace it. PipeWire/WirePlumber stay. |
| nmtui | Advanced network settings in a floating Ghostty window | Keep as a fallback; a basic Wi-Fi picker does not cover all connection types. |
| gnome-network-displays | Miracast UI/streaming, explicitly launched with AMD VA-API | Keep. Quickshell can replace the launch button, not the casting implementation. |

Sources: [common.lua](../hyprland-common/.config/hypr/common.lua) startup and
bindings; [bar configuration](../waybar/.config/waybar/config.jsonc);
[popup implementation](../waybar/.local/bin/waybar-popup.py);
[network menu](../waybar/.local/bin/network-menu.sh);
[VPN adapter](../waybar/.local/bin/vpn-status.sh);
[inhibitor](../waybar/.local/bin/keep-awake.sh);
[power actions](../wlogout/.config/wlogout/layout);
[wallpaper](../hyprland-common/.config/hypr/hyprpaper.conf).

## Feature parity checklist

### Launcher and keybinding browser

- Preserve Super+Space for apps and Super+F1 for shortcuts; retain all current
  Hyprland binding descriptions and generated workspace bindings.
- Read live bindings rather than inventing a second hardcoded shortcut list.
  Lua dispatcher arguments in `hyprctl -j binds` are opaque callback IDs; the
  descriptions are the meaningful labels.
- Use actual category headers outside selectable entries, with independent
  typography/margins, real column layout, and filtering by action/key/category.
- Keep app launching based on desktop entries, not shell evaluation of a display
  label. Account for icons, terminal apps, keyboard navigation, and launch errors.
  The reviewed Quickshell v0.3.2 documentation says `DesktopEntry.execute()` ignores
  terminal mode and field codes. Use an appropriately tested launch path rather
  than assuming that convenience method fully reproduces Wofi's application mode.
  Pin/verify the chosen Quickshell version and distribution build: the capability
  note covers v0.3.2, not a package already installed on this machine.

Sources: [keybinding panel](../hyprland-common/.config/hypr/scripts/keybindings.py),
[shared bindings](../hyprland-common/.config/hypr/common.lua),
[DesktopEntry API](https://quickshell.org/docs/v0.3.2/types/Quickshell/DesktopEntry).

### Bar and popups

- Preserve workspace activation and focused window title; handle both machine
  profiles and output changes, rather than creating one hardcoded primary bar.
- Preserve calendar month navigation/today/selection, audio 0–100% controls,
  mute, and the pavucontrol escape hatch.
- Preserve battery charging/warning/critical information, Wi-Fi/Ethernet state,
  Bluetooth connection/battery information, clock, and power controls.
- Preserve `env LIBVA_DRIVER_NAME=radeonsi gnome-network-displays`: its AMD
  override is intentional for the laptop's hybrid graphics.
- There is **no tray module or media-player widget** in the current Waybar
  configuration. A system tray, MPRIS controls, brightness OSD, or power-profile
  selector would be new features, not migration requirements. Media hardware
  keys already call `playerctl`; brightness hardware keys call `brightnessctl`.

Sources: [bar modules/actions](../waybar/.config/waybar/config.jsonc),
[popup behavior](../waybar/.local/bin/waybar-popup.py),
[hardware keys](../hyprland-common/.config/hypr/common.lua).

### Network, VPN, notifications

- Open Wi-Fi from NetworkManager's cache, with explicit rescan, saved/unsaved
  handling, strongest-AP deduplication, radio on/off, and error feedback.
- Passwords must not appear in process arguments or logs. Existing code passes
  them on stdin. Preserve retry behavior after failed newly created profiles.
- Preserve captive-portal detection and browser escape hatch.
- **Proton VPN remains the owner of its ephemeral connections.** Existing code
  opens `protonvpn-app` when available rather than tearing down its tunnel behind
  the daemon's back. Without Proton, ordinary persistent NM VPNs can be managed
  through NetworkManager.
- Notification cutover must leave only one owner for the freedesktop notification
  service. Preserve actions, replacement IDs, expiration, urgency, DND, and
  history/clear behavior as explicit implementation choices. Keep `notify-send`
  working for the network menu and screenshot wrapper.

Sources: [network policies](../waybar/.local/bin/network-menu.sh),
[VPN state](../waybar/.local/bin/vpn-status.sh),
[notification actions](../waybar/.config/waybar/config.jsonc),
[SwayNC timeout](../hyprland-common/.config/swaync/config.json),
[screenshot notifications](../hyprland-common/.local/bin/screenshot.sh).

## Nonvisual behavior that must not be lost

### Keep-awake is not a bar-window property

The existing helper holds a **logind idle inhibitor** in a transient user service,
survives bar reloads, watches the compositor's PID/start time, and releases when
the session ends. Manual suspend is still allowed. A surface-bound Wayland idle
inhibitor is not automatically equivalent. Keep this backend while changing the
button/status UI; move it before unstowing `waybar`.

Source: [keep-awake.sh](../waybar/.local/bin/keep-awake.sh).

### Separate monitor reconciliation from obsolete Waybar reloads

`lid-display.sh` both reconciles physical lid state against connected DRM outputs
and serializes Waybar SIGUSR2 reloads. It runs from lid bindings, monitor-added
events, delayed startup, and Hypridle resume hooks. Retain the monitor/lid logic,
its startup crash guard, and the `--all-on` greeter handoff. Retire only the
Waybar-specific reload section after the replacement bar correctly handles
hotplug/resume. Do **not** blindly replace `pkill waybar` with `pkill quickshell`;
that would also kill every menu and possibly the notification server.

Sources: [lid-display.sh](../hyprland-common/.config/hypr/scripts/lid-display.sh),
[startup hooks](../hyprland-common/.config/hypr/common.lua),
[resume hooks](../hyprland-common/.config/hypr/hypridle.conf).

### Keep lock and idle behavior stable

Hypridle dims after 150s, locks after 300s, turns displays off after 330s, and
suspends after 1800s. It honors Wayland/systemd inhibitors and invokes before/after
sleep hooks. The DPMS helper records a Lua-dispatch workaround; the dim helper
only lowers brightness and coordinates with optional Matrix hardware so automatic
dimming does not trigger a manual-brightness gauge. Keep both helpers.

The lock wrapper serializes launches, preserves password authentication, and
auto-detects optional fingerprint hardware without putting `pam_fprintd` in the
password conversation. A new lock UI must independently reproduce that behavior
and securely use the session-lock protocol; an overlay does not lock the session.
Keep the existing lock/PAM path in the initial migration.

Sources: [Hypridle policy](../hyprland-common/.config/hypr/hypridle.conf),
[DPMS helper](../hyprland-common/.config/hypr/scripts/dpms.sh),
[dimming helper](../hyprland-common/.config/hypr/scripts/idle-dim.sh),
[lock wrapper](../hyprland-common/.config/hypr/scripts/lock.sh),
[PAM installer](../install-pam-hyprlock.sh), [auth notes](../docs/hyprlock-auth.md).

### Hyprland's Lua IPC needs deliberate support

This repo uses `hyprland.lua`, `hl.dsp.*`, and `hyprctl eval`. Existing research
documents legacy textual dispatch incompatibilities. Do not assume an upstream
Quickshell example using `workspace 1` works with this compositor. Validate the
chosen integration/version; use compatible Lua dispatches where needed. Reading
IPC state and dispatching an action are separate compatibility questions.

Sources: [both machine profiles](../hyprland-mini-mecha/.config/hypr/hyprland.lua),
[desktop profile](../hyprland-oki-mecha/.config/hypr/hyprland.lua),
[prior IPC investigation](waybar-hyprland-workspace-clicks.md).

## Installer/configuration changes needed for a migration

1. **`setup.sh`:** introduce a Quickshell package/Stow item and shared dependencies;
   replace or retire the `waybar`, `wofi`, and `wlogout` menu items when cutover is
   complete. Wofi is also declared inside `PKGS[hyprland]`, so removing only its
   standalone item would reinstall it. SwayNC and Hyprpaper are likewise inside
   that Hyprland dependency list; change them only if their features are migrated.
2. **Startup:** replace the Waybar launch in `common.lua` with one explicit shell
   lifecycle owner. Initially keep SwayNC/Hyprpaper/Hypridle. Later remove SwayNC
   startup only during a controlled notification-server cutover. Preserve logging
   and prevent duplicate instances on config reload.
3. **Menu entry points:** route Super+Space, Super+F1, Super+Delete and bar buttons
   to the new shell's IPC actions. Keep all current shortcut descriptions.
4. **Stow ownership:** preserve `keep-awake.sh` outside `waybar/` before retiring
   that package. Decide whether to retain backend code or rewrite it before
   removing `network-menu.sh`/`vpn-status.sh`. Retire popup/CSS/Fuzzel/Wofi/wlogout
   assets only after parity and fallback testing.
5. **`setup-waybar.sh`:** obsolete after full cutover; it exists specifically to
   select a Lua-capable stable/Git Waybar build. Keeping it temporarily as a
   rollback installer is reasonable.
6. **`scripts/check_setup.py` and `SETUP-AUDIT.md`:** move expectations to the new
   Stow/package model. Retire the Waybar-specific version exception after it is no
   longer part of the supported setup. Preserve separate greetd/PAM checks.
7. **Tests/docs:** adapt keybinding and popup tests, add shell IPC/model/placement
   tests, retain inhibitor tests with its new path, and update host/setup audit
   tests plus the Waybar/menu documentation. Existing GTK popup test helpers do not
   establish correctness of a new Qt shell.

Sources: [registry/handlers](../setup.sh), [Waybar installer](../setup-waybar.sh),
[drift checker](../scripts/check_setup.py), [tests](../tests/),
[popup documentation](../docs/waybar-popups.md),
[shortcut documentation](../docs/hyprland-keybindings.md).

## Dependency removal boundaries

Potentially unnecessary **for this configuration after parity**: `wofi`, `waybar`
(or `waybar-git`), `wlogout`, `fuzzel`, and later `swaync`. `hyprpaper` is optional
only if the shell takes over wallpaper rendering. Installed packages should remain
available through staged testing/rollback; this is not an uninstall instruction.

Do not recursively remove the entire old Waybar dependency list:

- Keep `wireplumber`/PipeWire, NetworkManager, BlueZ, logind/systemd, and polkit.
- Keep `jq` for the current inhibitor and any retained shell scripts. Python is
  still used by the drift audit and other utilities even if the menus stop using it.
- `python-gobject`, `gtk3`, and `gtk-layer-shell` cease to be our popup's direct
  requirements, but other installed apps can still need them. GTK4/Nautilus and
  the GTK login greeter are not replaced by choosing a Qt desktop shell.
- Keep `libnotify`/`notify-send`, screenshot tools, `brightnessctl`, `playerctl`,
  `gnome-keyring`, `libsecret`, and `xdg-desktop-portal-hyprland` for their existing
  responsibilities. Keep Blueman/pavucontrol/nmtui/Miracast as advanced fallbacks.
- `polkit-gnome` is installed by both the Hyprland registry and
  `setup-nautilus.sh`, and checked by the Nautilus audit. A later polkit-agent
  replacement needs all three expectations updated, not just autostart.

Sources: [setup registry](../setup.sh), [Nautilus installer](../setup-nautilus.sh),
[audit package checks](../scripts/check_setup.py),
[capture wrapper](../hyprland-common/.local/bin/screenshot.sh).

## Outside the replacement scope

Keep greetd/ReGreet and `install-greetd-regreet.sh`: they run in a separate greeter
session, with root-owned configuration, separate PAM, monitor/HDR rules, and login
assets. A user-session shell does not replace the login manager. Keep the machine
monitor/GPU profiles. Background/avatar asset packages can feed both systems.

Terminal/Fish, Nautilus/GVfs/GTK preferences, gaming apps, optional Matrix hardware,
TTY configuration, Limine maintenance, the upall privilege gate, OpenCode, and
skill installers do not become obsolete. Quickshell does not replace them.

Sources: [greeter installer](../install-greetd-regreet.sh),
[standalone greeter config](../greetd-setup/etc/greetd/hyprland.lua),
[setup items](../setup.sh), [installer audit coverage](../SETUP-AUDIT.md).

## Recommended order

1. Build launcher and shortcut browser, keeping their existing shortcuts and
   live data. This directly fixes the styling issue without touching security.
2. Implement the bar, calendar/audio/power panels; keep advanced settings apps and
   the current notification/idle/lock/wallpaper services. Reuse the inhibitor.
3. Port the network UI and its policies, then cut over notifications separately.
4. Test laptop/desktop, keyboard navigation, multiple outputs/scales, hotplug,
   lid closed/open, suspend/resume, and shell crash/restart before retiring old
   launchers/bar assets. Specifically verify keep-awake survives shell restarts.
5. Consider wallpaper and polkit UI later. Treat replacing Hyprlock/Hypridle or
   the login greeter as separate projects, not prerequisites for a cohesive shell.
