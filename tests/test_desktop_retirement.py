"""Retirement deletes only owned links/masks, never real or foreign configs."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('retire_desktop', ROOT / 'scripts/retire_desktop.py')
retire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retire)


class RetirementTest(unittest.TestCase):
    def test_only_our_retired_links_are_selected_including_dangling_links(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / 'home'
            root = Path(directory) / 'repo'
            config = home / '.config'
            config.mkdir(parents=True)
            owned = config / 'waybar'
            owned.symlink_to(root / 'waybar/.config/waybar')
            foreign = config / 'wofi'
            foreign.symlink_to(Path(directory) / 'someone-else')
            real = config / 'swaync'
            real.mkdir()
            (real / 'local.json').write_text('keep')
            managed = real / 'style.css'
            managed.symlink_to(root / 'hyprland-common/.config/swaync/style.css')
            self.assertEqual(set(retire.retired_links(home, config, root)), {owned, managed})
            self.assertEqual((real / 'local.json').read_text(), 'keep')

    def test_mask_without_ownership_marker_is_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            unit = runtime / 'systemd/user/swaync.service'
            unit.parent.mkdir(parents=True)
            unit.symlink_to('/dev/null')
            self.assertFalse(retire.remove_owned_mask(runtime))
            self.assertTrue(unit.is_symlink())

    def test_owned_runtime_mask_is_removed_but_foreign_replacement_is_preserved(self):
        for target in ('/dev/null', '/foreign/service'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                runtime = Path(directory)
                unit = runtime / 'systemd/user/swaync.service'
                unit.parent.mkdir(parents=True)
                unit.symlink_to(target)
                marker = runtime / 'dotfiles-atelier-swaync-mask'
                marker.touch()
                self.assertTrue(retire.remove_owned_mask(runtime))
                self.assertEqual(unit.is_symlink(), target != '/dev/null')
                self.assertFalse(marker.exists())
