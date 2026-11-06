#!/usr/bin/env python3
"""Read-only, searchable view of the running compositor's bindings."""

from html import escape
import json
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
# Keep header-internal newlines inside a single Wofi entry.
ENTRY_SEPARATOR = "\x1f"


def category_header(category):
    accent = json.loads(Path(__file__).with_name("atelier-colors.json").read_text())["accent"]
    return f'<span size="small" foreground="{accent}">\n{escape(category)}\n</span>'


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
            if key in ("return", "e", "space", "b", "w", "g", "h"):
                return "Applications"
            if key in ("l", "backspace", "delete"):
                return "Session & power"
    return "Other"


def one_line(value):
    return " ".join(str(value).split())


def format_bindings(bindings):
    groups = {category: [] for category in CATEGORIES}
    for binding in bindings:
        modifiers = [name for mask, name in MODIFIERS if binding.get("modmask", 0) & mask]
        key = binding.get("key") or f'keycode:{binding.get("keycode", 0)}'
        shortcut = " + ".join(modifiers + [KEY_NAMES.get(key, key)])
        description = binding.get("description")
        if not description:
            # Lua dispatchers expose an internal callback ID, not a command.
            dispatcher = binding.get("dispatcher", "")
            description = dispatcher
            if not dispatcher.startswith("HL.Dispatcher("):
                description += " " + binding.get("arg", "")
        context = []
        if binding.get("submap"):
            context.append("submap: " + binding["submap"])
        for field, label in (("release", "on release"), ("longPress", "long press"),
                             ("repeat", "repeat"), ("locked", "works when locked")):
            if binding.get(field):
                context.append(label)
        suffix = "  [" + one_line(", ".join(context)) + "]" if context else ""
        category = category_for(binding)
        # Repeat the category on each row so filtering by it retains its bindings,
        # not just the heading. Wofi dmenu has no native non-selectable sections.
        groups[category].append(
            escape(f"{category:<19}   {one_line(shortcut):<30}   {one_line(description)}{suffix}")
        )
    rows = []
    for category, entries in groups.items():
        if entries:
            rows.append(category_header(category))
            rows.extend(entries)
    return ENTRY_SEPARATOR.join(rows)


def main():
    try:
        result = subprocess.run(["hyprctl", "-j", "binds"], check=True,
                                capture_output=True, text=True, timeout=5)
        rows = format_bindings(json.loads(result.stdout))
        # Dedicated config/style; all binding text is escaped before enabling markup.
        subprocess.run([
            "wofi", "--conf", "/dev/null", "--dmenu", "--insensitive",
            "--matching", "contains", "--location", "center",
            "--sort-order", "default",
            "--width", "1100", "--height", "70%",
            "--prompt", "Hyprland keybindings — type to filter · Esc to close",
            "--cache-file", "/dev/null", "--define", "allow_markup=true",
            "--parse-search", "--define", f"dmenu-separator={ENTRY_SEPARATOR}",
            "--define", "allow_images=false", "--define", "normal_window=false",
            "--style", str(Path(__file__).resolve().with_name("keybindings.css")),
        ], input=rows, text=True, stdout=subprocess.DEVNULL, check=False)
        # Enter/click only dismisses the reference; never execute a selection.
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError) as error:
        print(f"Cannot show Hyprland keybindings: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
