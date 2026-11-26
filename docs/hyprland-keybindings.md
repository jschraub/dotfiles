# Desktop and application shortcut reference

The [Atelier Quickshell desktop](atelier.md) provides the native shortcut
browser. Super+F1 always opens Atelier; the Wofi fallback is retired.

Use **Super+Arrow** to focus a neighboring window, and **Super+Shift+Arrow** to
move the focused tiled window left, right, up, or down within the layout.

Press **Super+F1** on either machine to open a centered Atelier panel. Type to filter
by shortcut or description (case-insensitive), scroll or use the arrow keys to
browse, and press **Esc** to close. The panel is reference-only; it never runs a shortcut.

## Workspace application tabs

The panel opens on the application focused before the overlay took keyboard
focus. **Desktop** remains a separate tab. Each application on the focused
workspace gets a tab; multiple windows with the same application class share
one tab with a window count. Pinned windows are included, hidden and unmapped
windows are excluded, and an active special workspace is respected.

Use **Ctrl+Tab / Ctrl+Shift+Tab** to cycle tabs. Tab/Shift+Tab moves keyboard
focus between controls. Left/right arrows navigate the application and terminal
tool buttons. Search and category filtering apply to the selected tab. Refresh
re-queries the workspace and configuration; tabs otherwise remain stable while
reading. Switching reference tabs never focuses or sends keys to real windows.

Green labels show direct keyboard access, including while search has focus:

| Shortcut | Action |
| --- | --- |
| Alt+D | Select Desktop in either view. |
| Alt+1…9 | Select the tab at that position. Desktop also retains Alt+D. |
| Alt+W / Alt+A | This workspace / All installed. |
| Alt+Shift+1…9 | Select a terminal-tool option when the terminal tab is selected. |
| Alt+S | Focus search. |
| Alt+R | Refresh the reference snapshot. |
| Ctrl+Tab / Ctrl+Shift+Tab | Next / previous tab, including tabs beyond the first nine. |

These are panel-local bindings, not new global Hyprland shortcuts. Unmodified
letters remain normal search input.

**This workspace** is the default view. Its application tabs show open windows
here, and its terminal-tool buttons show only detected workspace-local tools.
Installed but closed tools do not appear in that picker.

**All installed** opens a combined searchable reference plus individual
application/tool tabs. It includes installed tools whether open or closed, but
only where a shortcut profile exists. Installation is checked using executable
lookup on PATH, or established by a matching running application/tool. It never
runs a tool to test installation. A profile's optional `executables` list can
identify a launcher whose name differs from its process name. Closed Flatpak
apps or other launchers absent from PATH need a discoverable launcher match;
merely bundling a reference does not make an application appear installed.

Bundled profiles (available only when installed or running):

| Application/tool | Source and limits |
| --- | --- |
| Desktop | Live `hyprctl -j binds`. |
| Ghostty | `ghostty +list-keybinds --plain`, which reads configured bindings. Per-window command-line overrides are not inspected. Known actions are described; arbitrary text/command payloads are omitted. |
| OpenCode | Documented V2 defaults from [the keybind reference](https://opencode.ai/docs/cli/keybinds), checked November 25, 2026, plus `$XDG_CONFIG_HOME/opencode/cli.json`. Leader changes, alternatives, object bindings, and disabled keys are reflected. Session/environment/plugin overrides and unlisted command IDs are not inspected. |
| Zen | Common browser defaults. Custom Zen shortcuts and extensions are not inspected. |
| tmux | Documented defaults with Ctrl+B prefix. Hidden when not installed or detected running. Custom prefix, key tables, server sockets, and pane programs are not inspected. |

OpenCode and tmux are terminal-tool references inside Ghostty's tab. **Detected
tools** includes known foreground processes descended from the terminal process,
including children spawned by worker threads. Detection reads only owned
process metadata: process names, foreground process groups, and child PIDs.
It never reads command arguments, environments, shell history, terminal output,
or working directories.

Ghostty shares a process across windows/tabs. A detected tool is only treated as
workspace-local when every mapped window sharing that terminal process belongs
to the visible workspace. If a terminal process spans workspaces, its tools
are withheld rather than attributed to the wrong workspace. Even within one
workspace, detection does **not** establish the focused pane.
Use **Terminal only** to hide tool help, choose among the detected tools, or use
**All installed** to find other available references. Detached tmux servers,
remote SSH programs, and tools hosted outside the terminal process tree are
not discovered.

Unknown applications still get a tab, with an explicit missing-profile message
rather than invented bindings. Source labels distinguish configuration-derived
shortcuts, documented defaults, and user references.

## Add or replace a reference profile

Shared defaults live in
`quickshell/.config/quickshell/atelier/shortcut_profiles.json`. Optional
machine-local profiles live in `$XDG_CONFIG_HOME/atelier/shortcuts.json`
(`~/.config/atelier/shortcuts.json` by default).

For example, this replaces the built-in OpenCode reference with a short,
explicit list:

```json
{
  "profiles": [
    {
      "id": "opencode",
      "name": "OpenCode",
      "processes": ["opencode"],
      "bindings": [
        {
          "key": "Ctrl + P",
          "description": "Command palette",
          "category": "OpenCode"
        },
        {
          "key": "Ctrl + Alt + K",
          "description": "Toggle Which-Key help",
          "category": "OpenCode"
        }
      ]
    }
  ]
}
```

Profiles with the same `id` replace the whole built-in profile, not individual
rows. A user-supplied OpenCode profile is not merged with `cli.json`; its rows
are an explicit reference. Use `classes` for exact, case-insensitive Hyprland
application-class matches, or `processes` for terminal-tool matches against
Linux process names. Run `hyprctl -j activewindow | jq -r .class` in the app
to find its class. Each binding requires `key` and `description`; `category`
and `context` are optional.

`executables` optionally lists exact executable basenames for installation checks,
for example `"executables": ["opencode"]`. Without it, profile ID, process
names, and application classes are tried as executable names.

Profiles contain data only. There are no scripts, shell commands, regexes, or
automatic key execution. Keep credentials out of reference text. The custom
document is limited to 1 MiB, 32 profiles, and 500 rows per profile. Invalid
custom profiles leave built-ins intact and show a warning in the Desktop tab.
Refresh or reopen the panel after editing.

herdr can be added through this format once installed and its actual bindings
are known; no shortcuts are guessed for it.

## Maintain the Desktop tab

Desktop shortcuts are grouped under category headings (Applications, Window management,
Focus & movement, Workspaces, Screenshots, Audio & media, Brightness, and
Session & power). Category names are searchable too: type `workspaces` to show
just workspace shortcuts. A category sidebar and section headings organize separate
Shortcut and Description columns. Unknown shortcuts appear under Other. Headings
are amber; shortcut text is green. Keyboard hints use the same green accent.

The panel queries `hyprctl -j binds` each time, including generated workspace
bindings, mouse shortcuts, media keys, and lid switches. Keep new bindings readable
by adding `description = "What this does"` to the third argument of `hl.bind` in
`hyprland-common/.config/hypr/common.lua` (alongside any existing flags). No separate
shortcut list needs updating. Categories are inferred from shortcut keys in
`scripts/keybindings.py`; extend `category_for` when adding a new kind of shortcut.

Dependencies: Quickshell >=0.3.2, Python, and a running Hyprland session.
`setup.sh hyprland` installs/stows the native desktop and its shared helpers.

After updating an existing install, restow the shared package and reload:

```sh
stow -R -t "$HOME" -d "$HOME/dotfiles" hyprland-common
hyprctl reload
```

Run tests with:

```sh
python -B -m unittest discover -s tests -p test_keybindings.py -v
python -B -m unittest discover -s tests -p test_shortcut_context.py -v
ATELIER_GUI_TESTS=1 python -B -m unittest discover -s tests -p test_shortcut_context_gui.py -v
```
