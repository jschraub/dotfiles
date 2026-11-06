# Hyprland shortcut reference

The new [Atelier Quickshell desktop](atelier.md) provides the native shortcut
browser after activation. Super+F1 routes to the selected desktop; the Wofi
implementation below is retained for legacy mode/rollback.

Use **Super+Arrow** to focus a neighboring window, and **Super+Shift+Arrow** to
move the focused tiled window left, right, up, or down within the layout.

Press **Super+F1** on either machine to open a centered Wofi panel. Type to filter
by shortcut or description (case-insensitive), scroll or use the arrow keys to
browse, and press **Esc** to close. Enter or clicking a row only dismisses the
panel; it never runs the shortcut.

Shortcuts are grouped under category headings (Applications, Window management,
Focus & movement, Workspaces, Screenshots, Audio & media, Brightness, and
Session & power). Category names are searchable too: type `workspaces` to show
just workspace shortcuts. Each row has aligned Category, Shortcut, and Description
columns separated by whitespace. Unknown shortcuts appear under Other. Headings
use smaller peach-colored text with vertical whitespace. Wofi still treats them
as informational rows internally; selecting one also just closes the panel.

The panel queries `hyprctl -j binds` each time, including generated workspace
bindings, mouse shortcuts, media keys, and lid switches. Keep new bindings readable
by adding `description = "What this does"` to the third argument of `hl.bind` in
`hyprland-common/.config/hypr/common.lua` (alongside any existing flags). No separate
shortcut list needs updating. Categories are inferred from shortcut keys in
`scripts/keybindings.py`; extend `category_for` when adding a new kind of shortcut.

Dependencies: `python`, `wofi`, and a running Hyprland session. `setup.sh hyprland`
includes both packages. The panel has its own stylesheet, so the `wofi` stow
package is optional.

After updating an existing install, restow the shared package and reload:

```sh
stow -R -t "$HOME" -d "$HOME/dotfiles" hyprland-common
hyprctl reload
```

Run tests with `python -m unittest discover -s tests -p test_keybindings.py -v`.
