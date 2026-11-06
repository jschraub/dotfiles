# Waybar calendar and audio popups

- Click the date/time to open the calendar. Navigate months, select dates, or
  return to Today without closing it. Escape or an outside click dismisses it.
- Click the speaker to open a 0–100% output-volume slider and mute control.
  **Audio settings…** opens pavucontrol for devices, inputs, and per-app volume.
  Right-clicking the speaker still opens pavucontrol directly.
- A filled coffee cup means **keep awake**; an outlined cup means **allow sleep**.

Popups use GTK3 layer-shell surfaces, a Catppuccin Mocha theme, and the output
under the pointer. The transparent backdrop dismisses outside clicks (consuming
the dismissal click); it does not dim the desktop. Only one panel is open per
user, and invoking the same panel again toggles it closed. Audio state is queried
from WirePlumber while open; slider writes are debounced and never exceed 100%.
An externally amplified volume can still be displayed without changing it.

Dependencies are declared in `setup.sh` under `waybar`: `python-gobject`, `gtk3`,
`gtk-layer-shell`, `wireplumber`, and `pavucontrol`. Existing bar dependencies are
unchanged. Install/restow with `./setup.sh waybar`. If dependencies are already
present, restowing alone is enough:

```sh
stow --restow --target "$HOME" --dir "$HOME/dotfiles" waybar
```

Reload Waybar at a convenient time to pick up new click actions:

```sh
pkill -USR2 -x waybar
```

This does not reload Hyprland. The separate keep-awake service survives bar reloads.

Test models without a GUI or audio writes:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_waybar_popup.py -v
```

Optional graphical smoke tests briefly display an isolated panel, check that an
inside click stays open, then dismiss it with Escape or an outside-click event.
They check window/timer cleanup without changing volume or an existing popup:

```sh
~/.local/bin/waybar-popup.py calendar --smoke-test
~/.local/bin/waybar-popup.py audio --smoke-test
~/.local/bin/waybar-popup.py calendar --smoke-test outside
```

To run those checks plus real singleton switching/toggling (briefly opens panels,
never adjusts volume), explicitly opt in from your graphical session:

```sh
DOTFILES_GUI_TESTS=1 PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_waybar_popup.py -v
```

The singleton check skips rather than interfering if you already have a popup open.
