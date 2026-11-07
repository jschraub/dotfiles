#!/usr/bin/env python3
"""Read-only, searchable view of the running compositor's bindings."""

from pathlib import Path
import subprocess
import sys


MODIFIERS = ((64, "Super"), (4, "Ctrl"), (8, "Alt"), (1, "Shift"),
             (2, "Caps"), (16, "Mod2"), (32, "Mod3"), (128, "Mod5"))
KEY_NAMES = {
    "return": "Enter", "space": "Space", "backspace": "Backspace",
    "delete": "Delete", "mouse:272": "Left mouse", "mouse:273": "Right mouse",
    "mouse_down": "Scroll down", "mouse_up": "Scroll up",
}
CATEGORIES = (
    "Help", "Applications", "Window management", "Focus & movement",
    "Workspaces", "Screenshots", "Audio & media", "Brightness",
    "Session & power", "Other",
)


def category_for(binding):
    """Classify the shared config's shortcuts; keep unknown bindings visible."""
    key = binding.get("key", "").lower()
    if key.startswith("switch:"):
        return "Session & power"
    if key.startswith("xf86audio"):
        return "Audio & media"
    if key.startswith("xf86monbrightness"):
        return "Brightness"
    if key == "print":
        return "Screenshots"
    modifiers = binding.get("modmask", 0)
    if modifiers in (64, 65):  # Super, optionally Shift
        if key in ("left", "right", "up", "down", "mouse:272", "mouse:273"):
            return "Focus & movement"
        if key in ("s", "mouse_up", "mouse_down") or key in tuple("0123456789"):
            return "Workspaces"
        if key in ("q", "p", "j") or (key == "space" and modifiers == 65):
            return "Window management"
        if modifiers == 64:
            if key == "f1":
                return "Help"
            if key in ("return", "e", "space", "b", "w", "g", "h", "v"):
                return "Applications"
            if key in ("l", "backspace", "delete"):
                return "Session & power"
    return "Other"


def main():
    try:
        subprocess.run([str(Path.home() / '.local/bin/desktop-shell'), 'toggle', 'bindings'], check=True)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError) as error:
        print(f"Cannot show Hyprland keybindings: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
