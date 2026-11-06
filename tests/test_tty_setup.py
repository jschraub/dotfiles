"""TTY setup checks, isolated from /etc and the user's real Fish configuration.

Run: python -m unittest discover -s tests -p test_tty_setup.py -v
"""
import os
from pathlib import Path
import pty
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TTY_CONFIG = ROOT / "fish/.config/fish/tty.fish"


class TtySetupTest(unittest.TestCase):
    def test_installer_preserves_settings_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            console = root / "vconsole.conf"
            original = '# keyboard\nKEYMAP=us\nFONT=old\nXKBLAYOUT=us\n'
            console.write_text(original)
            # Relocate only /etc references; use a copied installer and config.
            installer = root / "setup-tty.sh"
            installer.write_text((ROOT / "setup-tty.sh").read_text().replace(
                "/etc/vconsole.conf", str(console)))
            source = root / "fish/.config/fish/tty.fish"
            source.parent.mkdir(parents=True)
            shutil.copy(TTY_CONFIG, source)
            config_dir = home / ".config/fish"
            config_dir.mkdir(parents=True)
            config = config_dir / "config.fish"
            config.write_text('# existing config\n')
            (config_dir / "tty.fish").write_text('# previous tty config\n')
            bin_dir = root / "bin"
            bin_dir.mkdir()
            for name, text in {
                "pacman": "#!/bin/sh\nexit 0\n",
                "sudo": '#!/bin/sh\nexec "$@"\n',
                "tty": '#!/bin/sh\necho "not a tty"\nexit 1\n',
            }.items():
                file = bin_dir / name
                file.write_text(text)
                file.chmod(0o755)
            env = dict(os.environ, HOME=str(home), PATH=f'{bin_dir}:{os.environ["PATH"]}')
            for _ in range(2):
                subprocess.run(["bash", str(installer)], env=env, check=True,
                               capture_output=True, text=True)
                link = config_dir / 'tty.fish'
                self.assertFalse(Path(os.readlink(link)).is_absolute())
                # Simulate the absolute link made by the original installer;
                # the next run must normalize it without backing it up again.
                if _ == 0:
                    link.unlink()
                    link.symlink_to(source)
            self.assertEqual(console.read_text(), original.replace('FONT=old', 'FONT=ter-v16n'))
            backups = list(root.glob('vconsole.conf.pre-tty.*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), original)
            self.assertEqual(config.read_text().count('and source ~/.config/fish/tty.fish'), 1)
            self.assertEqual((config_dir / 'tty.fish').resolve(), source)
            self.assertEqual(len(list(config_dir.glob('tty.fish.pre-tty.*'))), 1)
            if shutil.which('stow'):
                subprocess.run(['stow', '--simulate', '--restow', '--target', str(home),
                                '--dir', str(root), 'fish'], check=True, capture_output=True)

    def check_fish(self, term, interactive=True):
        # A PTY allows testing the real interactive-only palette path.
        master, slave = pty.openpty()
        try:
            command = f'''
                function fish_prompt; echo ORIGINAL; end
                function fish_right_prompt; echo ORIGINAL_RIGHT; end
                function ls; echo ORIGINAL_LS; end
                set -gx COLORTERM truecolor
                source {TTY_CONFIG}
                functions fish_prompt fish_right_prompt ls
                printf 'COLORTERM=%s\\n' "$COLORTERM"
            '''
            args = ['fish', '--no-config'] + (['--interactive'] if interactive else [])
            proc = subprocess.run(args + ['-c', command], stdout=slave,
                                  stderr=subprocess.PIPE, env=dict(os.environ, TERM=term))
            os.close(slave)
            slave = None
            chunks = []
            while True:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                chunks.append(chunk)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
            return b''.join(chunks).decode()
        finally:
            os.close(master)
            if slave is not None:
                os.close(slave)

    def test_console_gets_ascii_prompt_and_palette(self):
        output = self.check_fish('linux')
        self.assertNotIn('ORIGINAL', output)
        self.assertIn('--icons=never', output)
        import json
        palette = json.loads((ROOT / 'theme/palette.json').read_text())['ansi']
        self.assertIn('\x1b]P0' + palette[0][1:], output)
        self.assertIn('\x1b]Pf' + palette[15][1:], output)
        self.assertNotIn('COLORTERM=truecolor', output)

    def test_gui_and_noninteractive_shells_unchanged(self):
        for term, interactive in [('xterm-256color', True), ('linux', False)]:
            with self.subTest(term=term, interactive=interactive):
                output = self.check_fish(term, interactive)
                self.assertIn('ORIGINAL_RIGHT', output)
                self.assertIn('ORIGINAL_LS', output)
                self.assertIn('COLORTERM=truecolor', output)
                self.assertNotIn('\x1b]P', output)
