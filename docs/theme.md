# Atelier Amber: portable desktop appearance

Neutral graphite backgrounds and gray text; amber focus/selection, burnt orange
emphasis and red errors. Green/blue/cyan remain available for semantic feedback
and syntax, not primary desktop decoration.

## Install on another machine

Run from this checkout as your normal user:

```sh
HYPR_MACHINE=mini-mecha ./setup.sh hyprland quickshell ghostty fish nautilus zed opencode theme
# Or ./setup.sh all — theme is included by default.
./check-setup.sh --machine mini-mecha hyprland ghostty fish nautilus opencode theme
```

Use `oki-mecha` for the desktop profile. On an already provisioned machine,
`./setup.sh theme` installs dependencies and applies appearance. The user-only
`./setup-theme.sh` skips package operations; `--no-runtime` also skips GSettings
changes and compositor/Ghostty reloads. It never uses sudo, logs out, or kills apps.
Generated files ship alongside the sources, so another machine needs no runtime generator.

The installer honors `XDG_CONFIG_HOME`; existing Hyprland/Fish configuration and
the general audit still expect this repository's normal `~/.config` layout.
There are no username-specific theme paths.

## Coverage and reloads

| Surface | Behavior |
| --- | --- |
| Atelier | Generated `Theme.qml`; QML live reload, no shell restart |
| Hyprland | Generated Lua colors; validate before installer reload |
| Hyprlock | Generated `colors.conf`; next lock; PAM/idle unchanged |
| Ghostty | Custom theme and all 16 ANSI colors; font 10, opacity **0.85** |
| Fish/Tide | Gray segments with amber text; amber directory with dark text; new shell |
| Linux TTY | Same ANSI palette; ASCII/no truecolor; next console shell |
| GTK3 | Local Atelier theme based on built-in Adwaita-dark |
| GTK4/Nautilus | Named colors and libadwaita CSS variables; reopen apps |
| ReGreet | Standalone generated CSS; root-owned install below |
| Claude statusline | Shared generated truecolor palette; next status update |
| OpenCode V2 | Documented dark `system` theme derived from terminal palette |
| VS Code | Local Atelier Amber extension; may need **Developer: Reload Window** |
| Zed (default editor) | Generated Atelier Amber theme; preserves existing settings; see [Zed setup](zed.md) |
| Zen/Firefox | Browser chrome CSS in existing profiles; next browser start |

Ghostty edits aren't assumed to have reloaded automatically. The installer invokes
the running GTK app's `reload-config` D-Bus action, preserving terminals/jobs.
Manual fallback: **Ctrl+Shift+,**. `ghostty +show-config` checks startup settings,
not the pixels in an existing surface. No compositor-wide opacity is applied.

Ghostty's native tab bar and toast are separate GTK widgets, not ANSI terminal
colors. Its generated `atelier.css` is explicitly loaded using `gtk-custom-css`:
neutral tabs/toasts, a subtly raised active tab with amber text and a
two-pixel muted amber underline, and amber toast actions.
The theme installer and audit include this file; it does not repaint terminal
surfaces or override their opacity. The opt-in real-widget regression is:

```sh
ATELIER_GTK_TESTS=1 python3 -B -m unittest discover -s tests -p test_theme_gtk.py
```

Tide uses four grayscale roles progressing from lightest on the left to darkest
on the right: user `#404040`, clock `#333333`, Git `#262626`, and environment
`#191919`. All language/runtime/Docker items share that final environment shade,
leaving wider steps between the normally visible sections. Text remains amber.
The shades are defined in `theme/palette.json` under `promptBackgrounds`.
Hidden roles preserve the ordering. If multiple environment items are displayed,
they intentionally share their role's background; this does not change Tide's
tool detection or hide any items. The directory stays amber with
dark text; dirty Git keeps a dark-amber background with light text. The Git item
resets both its foreground and background when returning to a clean repository.

Browser setup discovers profiles through `profiles.ini`, links `chrome/atelier.css`,
adds an import to `userChrome.css`, and enables
`toolkit.legacyUserProfileCustomizations.stylesheets` in `user.js`. Existing CSS
and unrelated preferences are preserved. **Websites are unchanged.** Selectors may
need adjustment after browser updates; the installer does not restart browsers.

Chromium, Qt-specific apps, other Electron apps, Flatpak sandboxes and apps with
fixed internal themes aren't forcibly recolored. They may inherit dark preferences,
not exact colors. Legacy Waybar/Wofi/wlogout rollback assets retain their old theme.
GTK4 CSS variables require GTK 4.16+/libadwaita 1.6+ (current Arch/CachyOS). Do not
globally force `GTK_THEME`; the local GTK3 theme uses GTK's Adwaita-dark resources
and no downloaded Catppuccin dependency.

## Root-owned greeter

For an existing ReGreet installation, explicitly run:

```sh
./install-greetd-regreet.sh --theme-only
```

This uses sudo to back up/install only `/etc/greetd/regreet.css`, root:root 644.
It does not restart greetd, change PAM/authentication, enable services, or change
monitor policy, wallpaper or avatar. Applies at the next greeter start. The normal
`./setup.sh greetd` flow includes the CSS for a new installation. Editing this repo
does not update the installed root-owned greeter by itself.

## Backups and undo

Conflicting real files **and foreign symlinks** receive sibling
`.pre-atelier.TIMESTAMP` backups. JSONC edits preserve comments, editor fonts,
plugins, permissions and unrelated settings. GSettings are saved before changes to
`~/.local/state/atelier/gsettings.TIMESTAMP.json`. Repeated file installation is
idempotent; backups are made only when values actually differ.

Restore the specific local backup after inspecting it. For GSettings, restore each
saved value with `gsettings set org.gnome.desktop.interface KEY VALUE`. Restoring
browser `userChrome.css`/`user.js` backups disables its injected stylesheet; for
newly created files, remove only the Atelier import/preference after review.
Restore greeter CSS separately with sudo if installed. `desktop-shell legacy`
changes the shell, not application themes.

## Edit and verify

`theme/palette.json` is the single color source. `theme/templates/` holds CSS
layouts with semantic color tokens. Legacy Hyprland names are compatibility
aliases, not separate Catppuccin values.

```sh
python3 scripts/render_theme.py
python3 scripts/render_theme.py --check
python3 -B -m unittest discover -s tests
./check-setup.sh theme
```

The generator atomically replaces files so live watchers can't read truncated
Lua/QML/CSS. When adding roles, generate definitions **before** changing consumers.
Validate with `Hyprland --verify-config -c ~/.config/hypr/hyprland.lua`, then reload
and check `hyprctl configerrors`. Don't stage incompatible names in live modules.

Tests cover drift, neutral channels/contrast, JSONC preservation, fresh-home
installation, old GTK links, repeat installs, safe browser injection, Hyprland
role completeness and Ghostty readability settings. The audit checks generated
drift, links, GSettings and installed theme choices read-only. Runtime appearance
and other-machine hardware remain separate visual checks.
