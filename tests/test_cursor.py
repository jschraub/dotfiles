"""Pinned cursor installation without network, real HOME changes or compositor writes."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_cursor', ROOT / 'scripts/install_cursor.py')
cursor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cursor)


class CursorTest(unittest.TestCase):
    def archive(self, root):
        path = root / 'fixture.tar.xz'
        with tarfile.open(path, 'w:xz') as bundle:
            info = tarfile.TarInfo(cursor.THEME + '/cursors/left_ptr')
            contents = b'Xcur-fixture'
            info.size = len(contents)
            bundle.addfile(info, io.BytesIO(contents))
        return path

    def test_verified_install_preserves_existing_theme_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.archive(root)
            data = root / 'data'
            target = data / 'icons' / cursor.THEME
            target.mkdir(parents=True)
            (target / 'custom').write_text('preserve')
            with patch.object(cursor, 'SHA256', hashlib.sha256(archive.read_bytes()).hexdigest()), \
                    patch.object(cursor.urllib.request, 'urlopen') as download:
                cursor.install(data, root / 'cache', archive)
                backups = list(target.parent.glob(cursor.THEME + '.backup-*'))
                self.assertEqual(len(backups), 1)
                self.assertEqual((backups[0] / 'custom').read_text(), 'preserve')
                self.assertEqual((target / 'cursors/left_ptr').read_bytes(), b'Xcur-fixture')
                cursor.install(data, root / 'cache')
                download.assert_not_called()
                self.assertEqual(len(list(target.parent.glob(cursor.THEME + '.backup-*'))), 1)

    def test_bad_checksum_writes_no_theme(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.archive(root)
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                cursor.install(root / 'data', root / 'cache', archive)
            self.assertFalse((root / 'data').exists())

    def test_cursor_selection_agrees_across_clients(self):
        for relative in ('desktop-theme/.config/gtk-3.0/settings.ini', 'gtk-4.0/.config/gtk-4.0/settings.ini'):
            text = (ROOT / relative).read_text()
            self.assertIn('gtk-cursor-theme-name=' + cursor.THEME, text)
            self.assertIn('gtk-cursor-theme-size=24', text)
        common = (ROOT / 'hyprland-common/.config/hypr/common.lua').read_text()
        self.assertIn('hl.env("XCURSOR_THEME", "' + cursor.THEME + '")', common)
        self.assertIn('hyprctl setcursor ' + cursor.THEME + ' 24', common)
