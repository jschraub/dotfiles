# Hyprland shortcut reference

The [Atelier Quickshell desktop](atelier.md) provides the native shortcut
browser. Super+F1 always opens Atelier; the Wofi fallback is retired.

Use **Super+Arrow** to focus a neighboring window, and **Super+Shift+Arrow** to
move the focused tiled window left, right, up, or down within the layout.

Press **Super+F1** on either machine to open a centered Atelier panel. Type to filter
by shortcut or description (case-insensitive), scroll or use the arrow keys to
browse, and press **Esc** to close. The panel is reference-only; it never runs a shortcut.

Shortcuts are grouped under category headings (Applications, Window management,
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

Run tests with `python -m unittest discover -s tests -p test_keybindings.py -v`.
