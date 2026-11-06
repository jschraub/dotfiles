"""Searchable shortcut reference: no GUI or running compositor required."""
import importlib.util
from html import unescape
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "hyprland-common/.config/hypr/scripts/keybindings.py"
SPEC = importlib.util.spec_from_file_location("keybindings", SCRIPT)
panel = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(panel)


class KeybindingsTest(unittest.TestCase):
    def test_shortcuts_descriptions_and_context(self):
        rows = panel.format_bindings([
            dict(modmask=65, key="space", description="Toggle floating window"),
            dict(modmask=64, key="mouse:272", description="Drag window"),
            dict(key="XF86AudioMute", description="Mute", locked=True, repeat=True),
            dict(modmask=12, keycode=38, dispatcher="exec", arg="example", submap="resize",
                 release=True, longPress=True),
        ])
        for text in ["Super + Shift + Space", "Toggle floating window",
                     "Super + Left mouse", "XF86AudioMute", "works when locked",
                     "repeat", "Ctrl + Alt + keycode:38", "exec example",
                     "submap: resize", "on release", "long press"]:
            self.assertIn(text, rows)

    def test_lua_fallback_does_not_show_internal_callback_as_command(self):
        rows = panel.format_bindings([dict(key="F2", dispatcher="HL.Dispatcher(exec_cmd)", arg="123")])
        self.assertIn("HL.Dispatcher(exec_cmd)", rows)
        self.assertNotIn("123", rows)

    def test_one_row_per_binding_including_switches_and_duplicates(self):
        binding = dict(key="switch:on:Lid Switch", description="Lid\nclosed\t action")
        self.assertEqual(len(panel.format_bindings([binding, binding]).split(panel.ENTRY_SEPARATOR)), 3)
        self.assertIn("Lid closed action", panel.format_bindings([binding]))

    def test_groups_follow_category_order_and_keep_unknown_bindings(self):
        rows = panel.format_bindings([
            dict(key="XF86AudioMute", description="Mute"),
            dict(key="unknown", description="Custom action"),
            dict(modmask=64, key="e", description="Files"),
            dict(modmask=65, key="left", description="Move left"),
            dict(modmask=64, key="return", description="Terminal"),
        ]).split(panel.ENTRY_SEPARATOR)
        self.assertEqual([row for row in rows if row.startswith("<span")], [
            panel.category_header(category) for category in
            ["Applications", "Focus & movement", "Audio & media", "Other"]
        ])
        self.assertIn("Files", rows[1])
        self.assertIn("Terminal", rows[2])
        self.assertEqual(rows[1], f'{"Applications":<19}   {"Super + e":<30}   Files')
        self.assertIn("Custom action", rows[-1])

    def test_category_and_shortcut_columns_are_aligned(self):
        rows = panel.format_bindings([
            dict(modmask=64, key="return", description="Terminal"),
            dict(modmask=65, key="space", description="Toggle floating window"),
        ]).split(panel.ENTRY_SEPARATOR)
        entries = [unescape(row) for row in rows if not row.startswith("<span")]
        self.assertEqual(entries[0][22:52].rstrip(), "Super + Enter")
        self.assertEqual(entries[1][22:52].rstrip(), "Super + Shift + Space")
        self.assertEqual(entries[0][55:], "Terminal")
        self.assertEqual(entries[1][55:], "Toggle floating window")
        self.assertNotIn("│", "".join(entries))

    def test_headers_have_accent_small_text_and_vertical_spacing(self):
        header = panel.category_header("Focus & movement")
        self.assertIn('size="small"', header)
        accent = json.loads((ROOT / 'theme/palette.json').read_text())['colors']['accent']
        self.assertIn(f'foreground="{accent}"', header)
        self.assertIn("\nFocus &amp; movement\n", header)

    def test_binding_markup_is_escaped(self):
        rows = panel.format_bindings([dict(key="<key>", description='<b>Not bold</b> & safe')])
        self.assertIn("&lt;key&gt;", rows)
        self.assertIn("&lt;b&gt;Not bold&lt;/b&gt; &amp; safe", rows)
        self.assertNotIn("<b>", rows)

    def test_category_classification(self):
        for key, modifiers, category in [
            ("F1", 64, "Help"), ("space", 64, "Applications"),
            ("space", 65, "Window management"), ("Q", 64, "Window management"),
            ("left", 64, "Focus & movement"), ("right", 65, "Focus & movement"),
            ("mouse:272", 64, "Focus & movement"), ("0", 65, "Workspaces"),
            ("S", 64, "Workspaces"), ("mouse_down", 64, "Workspaces"),
            ("Print", 1, "Screenshots"), ("XF86AudioPlay", 0, "Audio & media"),
            ("XF86MonBrightnessUp", 0, "Brightness"), ("L", 64, "Session & power"),
            ("switch:on:Lid Switch", 0, "Session & power"), ("E", 4, "Other"),
        ]:
            with self.subTest(key=key, modifiers=modifiers):
                self.assertEqual(panel.category_for(dict(key=key, modmask=modifiers)), category)

    def test_empty_bindings_have_no_headings(self):
        self.assertEqual(panel.format_bindings([]), "")

    @patch.object(panel.subprocess, "run")
    def test_panel_is_searchable_and_selection_is_never_executed(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 0, json.dumps([
            dict(key="F1", description="Show keybindings")
        ])), subprocess.CompletedProcess([], 0, "dangerous command")]
        self.assertEqual(panel.main(), 0)
        self.assertEqual(run.call_count, 2)
        args, kwargs = run.call_args
        self.assertEqual(args[0][0], "wofi")
        for option in ["--dmenu", "--insensitive", "contains", "center", "allow_markup=true",
                       "--parse-search", f"dmenu-separator={panel.ENTRY_SEPARATOR}"]:
            self.assertIn(option, args[0])
        self.assertEqual(args[0][args[0].index("--sort-order") + 1], "default")
        self.assertEqual(args[0][args[0].index("--width") + 1], "1100")
        self.assertIn("Show keybindings", kwargs["input"])
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)

    @patch.object(panel.subprocess, "run")
    def test_escape_is_normal(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 0, "[]"),
                           subprocess.CompletedProcess([], 1)]
        self.assertEqual(panel.main(), 0)

    @patch.object(panel.subprocess, "run")
    def test_failed_query_does_not_open_empty_panel(self, run):
        run.side_effect = subprocess.CalledProcessError(1, "hyprctl")
        with patch("sys.stderr"):
            self.assertEqual(panel.main(), 1)
        self.assertEqual(run.call_count, 1)

    @unittest.skipUnless(shutil.which("lua"), "lua required to evaluate the shared config")
    def test_all_configured_bindings_have_descriptions(self):
        config_dir = ROOT / "hyprland-common/.config/hypr"
        # Dispatchers are opaque objects to hl.bind; no compositor actions run.
        lua = '''
            local dummy
            dummy = setmetatable({}, {
                __index = function() return dummy end,
                __call = function() return dummy end,
            })
            hl = setmetatable({ dsp = dummy }, { __index = function() return function() end end })
            local moves = {}
            hl.dsp = setmetatable({ window = setmetatable({
                move = function(options) return { move = options } end,
            }, { __index = function() return dummy end }) }, { __index = function() return dummy end })
            local count = 0
            hl.bind = function(keys, action, options)
                assert(options and options.description and #options.description > 0, keys)
                count = count + 1
                if keys == "SUPER + F1" then print(options.description) end
                local direction = keys:match("^SUPER %+ SHIFT %+ (%a+)$")
                if direction == "left" or direction == "right" or direction == "up" or direction == "down" then
                    assert(action.move.direction == direction, keys)
                    assert(not moves[direction], "Duplicate movement binding: " .. keys)
                    moves[direction] = true
                end
            end
            package.path = arg[1] .. "/?.lua;" .. package.path
            require("common")
            for _, direction in ipairs({ "left", "right", "up", "down" }) do
                assert(moves[direction], "Missing movement binding: " .. direction)
            end
            print(count)
        '''
        result = subprocess.run(["lua", "-", str(config_dir)], input=lua,
                                text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout.splitlines(), ["Show searchable Hyprland keybindings", "64"])


if __name__ == "__main__":
    unittest.main()
