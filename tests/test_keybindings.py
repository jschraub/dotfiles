"""Searchable shortcut reference: no GUI or running compositor required."""
import importlib.util
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

    @patch.object(panel.subprocess, "run")
    def test_panel_is_searchable_and_selection_is_never_executed(self, run):
        self.assertEqual(panel.main(), 0)
        run.assert_called_once_with([str(Path.home() / '.local/bin/desktop-shell'), 'toggle', 'bindings'], check=True)

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
        self.assertEqual(result.stdout.splitlines(), ["Show searchable Hyprland keybindings", "72"])


if __name__ == "__main__":
    unittest.main()
