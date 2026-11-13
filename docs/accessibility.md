# Atelier accessibility pass

This pass improves the native shell's keyboard operation, focus visibility,
accessible names, contrast, scaling behavior and optional reduced motion. It is
not a claim of complete WCAG compliance or verified screen-reader compatibility.

## Keyboard access

The topbar does not steal keyboard focus from applications. Open its panels with
these shortcuts, also listed in **Super+F1**:

| Shortcut | Panel |
| --- | --- |
| Super+Space | Applications |
| Super+Ctrl+A | Sound (audio devices/microphone are accessible from here) |
| Super+Ctrl+N | Connectivity |
| Super+Ctrl+B | Bluetooth |
| Super+Ctrl+C | Calendar |
| Super+Ctrl+H | Notification history |
| Super+Ctrl+M | Media |
| Super+Ctrl+T | System tray |
| Super+V | Clipboard |
| Super+Delete | Session and power |

- Panels give initial focus to their search field or first enabled control.
- **Tab / Shift+Tab** cycle inside the open panel, skipping hidden/disabled
  controls. Focused controls scroll into view, including nested device lists.
- **Up/Down** move through application, network, device, Bluetooth, tray,
  notification and shortcut-category lists. Search fields retain their existing
  navigation behavior; virtualized lists bring further rows into view.
- Calendar dates support **Left/Right** for a day and **Up/Down** for a week,
  including crossing a month boundary.
- **Space / Enter** activate buttons, alongside the existing explicit
  launcher/clipboard/power shortcuts. **Escape** closes
  desktop panels without moving focus into the underlying application first.
- Keyboard focus gets an amber outline; sliders get a ring around the handle.
  Mouse focus alone does not leave a button outline. Selected workspaces keep
  their existing persistent outline.
- Button descriptions/tooltips appear on keyboard focus as well as hover.
  Shortcut hints remain green, without adding Power keycap backgrounds.
- Power shortcuts remain immediate: opening the panel and pressing **S** shuts
  down without an additional confirmation. Do not use real Power actions to
  casually test keyboard navigation.

## Names, states and contrast

Icon-only controls have action names rather than private-use glyphs. Slider names
identify output/microphone volume; search fields use their placeholder as a
default accessible name; repeated device actions identify the device. Panels
have names, calendar dates expose the complete date, and selection/toggle state
is exposed where meaningful. Descriptions never include password response text.

Normal text roles (`text`, `muted`, `accent`, `good`) have at least **4.5:1** contrast
against background, panel, raised and hover surfaces. Destructive button labels
use a brighter derivative of the existing semantic red to meet that threshold
on hover/raised backgrounds. Adjacent-month dates use readable muted text rather
than reducing the entire control to 35% opacity. Disabled controls and decorative
separators are not covered by the ordinary-text contrast assertion.

## Scaling and motion

Qt already follows output scaling. The shell now has an outer scrolling viewport
so a small logical display does not simply clip a panel's footer or controls.
Buttons and input fields also retain sufficient height for their text. Fake-panel
tests exercise **100%, 150% and 200% Qt scale**, including a restricted-height
viewport and nested scrolling. This is whole-interface scaling, not a new
text-only preference; GTK's text-scaling preference does not control these QML
pixel-sized fonts.

Set `ATELIER_REDUCED_MOTION=1` in the environment **before launching Quickshell**
to disable the shell's decorative button-color and scrollbar-fade animations.
The option does not remove hover/selection/focus feedback, delays used for input
debouncing, or user-controlled scrolling. For an existing Hyprland configuration,
the environment setting uses its normal Lua form:

```lua
hl.env("ATELIER_REDUCED_MOTION", "1")
```

This affects newly launched processes; it does not change an already-running
Quickshell instance's startup environment. Make session-environment changes for a
future login; do not restart a live locker to apply visual preferences. Optional
`QT_SCALE_FACTOR` is also a process startup setting and scales the whole Qt UI;
prefer normal per-output scaling when possible. No machine monitor profile was
changed by this pass.

## Authentication and rollout

Authentication conversation handling, password clearing, fingerprint policy,
session-lock ownership and power confirmation policy are unchanged. Shared
button/input labels, contrast and reduced-motion support also apply to copied
native login/lock UI, but root-owned copies are **not** updated by Stow. Use the
updater's separately approved authentication refresh while unlocked. The native
bundle remains self-contained: it does not import the desktop's `Focus.js`.

After updating, verify on both machines:

1. Open every panel from its shortcut and use only Tab/Shift+Tab/arrows/Escape.
2. Check long names, disabled devices, empty lists and a large notification history.
3. Verify output scaling and a small laptop/external display without clipped focus.
4. Test real login/lock keyboard operation on every output after refreshing copies.
5. With your preferred screen reader/AT-SPI setup, verify names, state changes,
   focus announcements and protected password entry. This final assistive-
   technology integration check has **not** been performed automatically.

Automated tests use fake apps/devices/notifications and temporary Quickshell
windows. They never authenticate, lock, change real devices or touch the clipboard:

```sh
ATELIER_GUI_TESTS=1 python3 -B -m unittest discover -s tests -p test_accessibility.py
```

Remaining follow-ups include an in-shell persistent text-size/motion preference,
live screen-reader testing, and broader mixed-DPI/hardware coverage. The reduced-
motion option is explicit, not an automatic subscription to desktop GSettings.
