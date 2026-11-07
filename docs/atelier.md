# Atelier: a cohesive Quickshell desktop

Atelier replaces the collection of separately styled desktop menus with one
QML shell. The direction is intentionally not a copy of the previous Catppuccin
configuration: neutral graphite surfaces, light-gray text, vivid amber accents,
Inter typography, compact controls, and consistent 12px panel offsets. Styles
are semantic tokens generated into `quickshell/.config/quickshell/atelier/Theme.qml`
from `theme/palette.json`. See [desktop-wide theme setup](theme.md) for the shared
application palette, installer, backups and other-machine deployment.

The right side groups **Sound → Connectivity → Energy → Notifications → Clock →
Session/power**, with compact 4px gaps between groups and tighter spacing within
them. Buttons size to their content with 10px padding on each side. Content reserves
space for both the font advance and visible glyph bounds, so fallback icons are
visually centered without overflowing the content area. Volume and clock retain
tabular digits but have no reserved widths. Connectivity is a single icon for
wired, wireless, VPN protection or disconnection; full connection/IP/VPN details
remain in its hint and panel. Inactive
icons are subdued, with accents reserved for active connections, protection,
keep-awake, DND/notifications, charging and low battery. Cast lives in the
Connectivity panel rather than taking permanent bar space. Bluetooth also lives
there, with on/off/connected status and access to its full device manager.

## Install and start

Run from this checkout, as your normal user:

```sh
./setup.sh quickshell
desktop-shell start
```

Installation asks for package-manager authorization and stows the shared helpers
and Quickshell configuration. It does not restart the live desktop or uninstall
anything. Atelier is now the only desktop UI and starts at the next Hyprland login.
It also installs Inter and a desktop-entry terminal helper;
the stowed `~/.config/xdg-terminals.list` selects Ghostty for terminal apps.
Existing conflicting real files are backed up by the normal setup machinery.

`desktop-shell start` (also `activate`) is idempotent: it preserves a healthy live
shell, starts a missing one, and checks notification ownership without D-Bus
activation. Failure reports an error; there is no alternate desktop. Menu shortcuts
attempt native recovery if the shell has crashed. `desktop-shell preview` is only
available when no Atelier instance is running and does not claim notifications;
its controls still perform real actions. Quit preview with Ctrl+C before starting.
The real bar is at the **top**; utility panels open consistently underneath its
right edge on the clicked output. Launchers/reference/power panels open centered
on the focused or clicked output. Menus dismiss with Escape or an outside click.

## Retire the previous desktop

After validating the native desktop on each machine, run from a terminal:

```sh
./scripts/cleanup-atelier.sh
```

The three-stage wizard checks shell/wallpaper/authentication/notification health,
previews and confirms removal of **Waybar, SwayNC, Wofi, wlogout, Fuzzel, Hyprpaper
and polkit-gnome**, then removes only this checkout's retired symlinks and owned
runtime mask. Pacman uses `-R`, never recursive dependency/orphan removal or
dependency bypass. Sudo reads the password directly in your terminal. Foreign
links, real configs, persistent service policy and core backends are preserved.
On another machine, update/stow the new setup and start a fresh session first so
the native-only polkit supervisor has replaced the old fallback supervisor.
The old setup entries, UI assets, rollback mode and fallback watchers are retired.

**Retained, not fallbacks:** Blueman supplies pairing/PIN dialogs; pavucontrol
supplies per-app routing, profiles and ports; gnome-network-displays supplies
casting. Removing them would remove features that Atelier still delegates.

## Controls and parity

| Entry point | Behavior |
| --- | --- |
| Super+Space / Applications button | Desktop-entry launcher, icons, substring filtering, arrow-key navigation, Enter to launch; Gio handles Exec/DBus/Terminal semantics instead of evaluating labels as shell commands. |
| Super+F1 / launcher footer | Live shortcuts, category sidebar, real section headers, separate key/action columns, category/action/key filtering. Arrow/PageUp/PageDown scrolling; reference only, never executes shortcuts. |
| Super+V | Searchable RAM-only clipboard picker for text and PNGs, thumbnails, keyboard selection, copy/delete, pause and clear. Copy never automatically pastes. Source-marked sensitive offers are skipped; unmarked secrets can still be remembered. See [clipboard privacy and limits](clipboard.md). |
| Workspace buttons | Selected: amber number, amber outline and raised background. Occupied but unselected: amber number only; empty: muted number. Occupancy uses the compositor's actual window count on that output, not merely a workspace record. Hover/keyboard-focus cues remain; hints show window counts. Compact padding keeps numbers centered and multi-digit labels expand instead of clipping. Bars follow output creation/removal. |
| Volume in the bar | Always-visible volume/mute state; hovering and scrolling adjusts five percentage points per notch; click opens the 0–100% slider and mute. Scrolling the slider uses the same steps; right-click or Advanced opens pavucontrol. Unavailable state is explicit. |
| Network | Wi-Fi/Ethernet connection/IP, cached SSID list, signal/security/saved state, rescan, Wi-Fi on/off, masked password entry, captive-portal sign-in, advanced nmtui. Height follows content rather than filling a large empty panel. |
| VPN | Protected indicator when active; launching Proton dismisses Connectivity and the app remains responsible for Proton connections. Ordinary persistent NM VPNs can be connected/disconnected in place when Proton is absent. |
| Audio devices & microphone | Native PipeWire discovery and default output/input selection, microphone volume/mute; advanced routing remains in pavucontrol. |
| Bluetooth (inside Connectivity) | Adapter on/off, discovery with owned-scan cleanup, paired-device connections and battery/status. Advanced / Pair opens Blueman for pairing/PIN workflows; never auto-pairs/trusts devices. |
| Media & tray | Native MPRIS playback/player controls and StatusNotifier activation/nested DBusMenu menus. Bar controls appear only when players/items exist. |
| Hardware keys / OSD | Volume/microphone/brightness helpers work without the shell; OSDs appear only after explicit controls, never polling or automatic idle dimming. |
| Cast (inside Connectivity) | Launches gnome-network-displays with the existing AMD VA-API override. |
| Keep-awake cup | Reuses the session-scoped logind inhibitor; survives shell reload/restart and permits manual suspend. |
| Battery | Capacity, charging state and critical color when a battery exists; hidden on desktops without batteries. |
| Clock | Date/time and month calendar with navigation, selection and Today. Compact clock/network labels on narrower outputs. |
| Notifications | Top-right toasts, notification center/history, actions, images, replacement IDs, expiration, transient notifications, clear/dismiss and DND. Bell is outlined with empty history, filled when history has notifications, and crossed out in DND. Right-click toggles DND; critical notifications bypass it. |
| Super+Delete / power button | Lock receives initial keyboard focus. Arrow keys navigate the 2×2 grid; Tab cycles and Enter/Space activates. Green L/E/R/S shortcuts immediately run lock/logout/restart/shutdown and close the menu, with no confirmation step. Escape closes without acting. Lock still calls the shared Hyprlock wrapper; logout restores displays before ending the session. |

Notification history is bounded to 100 entries and is in memory for the running
shell. Active notifications survive QML reload through Quickshell's tracking;
expired history and DND do not persist across a full shell restart. Inline reply,
notification body HTML/hyperlinks and action icons are intentionally not
advertised. Notification text is rendered as plain text.

## What remains unchanged

Native login/locking replacements are available through the explicit staged
[Atelier access-screen migration](atelier-access.md). They are not activated by
desktop-shell cleanup or ordinary Quickshell setup.

Hyprland and its machine-specific GPU/monitor rules, Hypridle, Hyprlock/PAM and
optional fingerprint handling, the polkit service, gnome-keyring,
NetworkManager/Proton, BlueZ, PipeWire/WirePlumber, screenshots, portals, Miracast,
greetd/ReGreet, terminals and file manager remain in place. No root-owned
authentication, greeter, idle/suspend or networking policies are replaced.

Quickshell renders each machine's configured wallpaper only after decoding the
image; Hyprpaper and its watcher are removed. See [wallpapers](wallpapers.md).
Native authentication runs in a separate `auth.qml` process. `desktop-polkit`
restarts crashed/unregistered native agents, with no GNOME-agent fallback.
Responses go directly to polkit, never backend, argv, IPC or logs. Authentication
fails closed while the agent is unavailable. There is no password-response IPC.

`lid-display.sh` keeps its real lid/DRM reconciliation, startup safety guard and
greeter handoff. The obsolete Waybar reload section is removed; Atelier follows
`Quickshell.screens` without restarting the shell.

The inhibitor now lives at `~/.local/bin/dotfiles-keep-awake.sh`, provided by
`hyprland-common`, independent of the shell process.

## Structure and maintenance

- `shell.qml`: state/IPC coordination and shell-owned backend lifetime.
- `Bar.qml`, `MenuWindow.qml`: output-aware surfaces and placement.
- `BarControls.qml`: compact, content-sized right-side controls and state styling.
- Feature panels: independently styled QML components; no fake Wofi rows/markup.
- `VolumeWheel.qml`: shared wheel input for the audio button and slider. Small
  angle/pixel deltas accumulate; relative volume commands avoid stale UI readings.
  Audio operations are queued in input order in the adapter, and slider dragging
  and ordinary button clicks remain available through the wheel-only overlay.
- `Theme.qml`, `Label.qml`, `ActionButton.qml`, `SearchField.qml`: shared visuals.
- `NotificationService.qml`: native freedesktop notification service and policy.
- `backend.py`: allowlisted JSON-lines adapter for Gio, Lua Hyprland IPC, nmcli,
  wpctl and the existing inhibitor. Hyprland socket events update focus/workspaces
  promptly; slower system status is refreshed separately on a two-second cadence
  and after control actions. Passwords pass over stdin, never argv or logs.
- `DesktopServices.qml`: native PipeWire, BlueZ, MPRIS and tray discovery.
- `hyprland-common/.local/bin/desktop-shell`: idempotent native lifecycle and
  menu-triggered recovery; startup failures are explicit.
- `desktop-polkit`: session-locked native agent supervision and registration checks.
- `desktop-control`: serialized hardware-key actions and manual-only OSD events.

Dependencies are declared under `quickshell` in `setup.sh`; a versioned package
check requires Quickshell >=0.3.2. NetworkManager/BlueZ must already be configured
as the machine's service backends; this installer does not silently enable new
system services or change network management on an existing installation.

Inspect state/logs:

```sh
desktop-shell mode
qs ipc -c atelier call shell status
qs log -c atelier
./check-setup.sh quickshell hyprland
```

The audit checks files/packages, not live feature or hardware behavior.
After changing QML, Quickshell reloads it automatically. Backend restarts are
shell-owned; the keep-awake inhibitor is deliberately not shell-owned.

## Verification

```sh
python -B -m unittest discover -s tests
ATELIER_GUI_TESTS=1 python -B -m unittest discover -s tests -p test_atelier_gui.py -v
ATELIER_NOTIFICATION_TESTS=1 python -B -m unittest discover -s tests -p test_atelier_notifications.py -v
```

GUI smoke tests temporarily open a bottom preview bar and each panel but never
activate the desktop or change system settings. The hover regression briefly
moves the pointer over a temporary test button, verifies its hint stays below the
button rather than following the pointer, and restores the pointer afterward.
Hints use native Quickshell popup surfaces with an 8px gap below the button, a
600ms delay, wrapped text, and screen-edge adjustment. Notification integration uses a
**private D-Bus session** and never takes the real notification name from SwayNC.
Both support `ATELIER_QS_BINARY` for an isolated Quickshell binary.

The audio wheel regression uses real Qt mouse-wheel events over the production
button/slider with a fake backend. It checks individual and rapid steps, bounds,
precision deltas, touchpad-delta accumulation, slider input geometry, click-through
and dragging without touching real audio. Backend tests separately cover relative
`wpctl` commands, ordered audio execution and draining work before adapter shutdown.

Automated coverage includes fake-device audio/Bluetooth/auth controls, native
MPRIS/tray/nested-menu integration on a private bus, wallpaper readiness, native
agent retry and retirement ownership checks. Native polkit cancellation has also
been exercised live without credentials or privileged execution. The user approved
the manual spot-check list before retirement; automation does not change real
volume/pairing/power state. Validate a fresh login after cleanup on each machine.

One tested API edge: v0.3.2's `Notification.expireTimeout` returns protocol
**milliseconds**, despite its online documentation saying seconds. The private
D-Bus replacement/expiration test protects against that mismatch on upgrades.

See [migration audit](../research/quickshell-setup-audit.md) and
[upstream capability notes](../research/quickshell-capabilities.md) for the original
scope and source evidence.
