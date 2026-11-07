"""Service handoff/control tests with fake processes and temporary files only."""
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / relative))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


backend = load('atelier_extended_backend', 'quickshell/.config/quickshell/atelier/backend.py')
polkit = load('atelier_polkit', 'hyprland-common/.local/bin/desktop-polkit')


class DesktopExtensionsTest(unittest.TestCase):
    @patch.object(backend, 'command')
    def test_microphone_controls_target_input_not_output(self, command):
        backend.action({'action': 'mic-mute'})
        command.assert_called_with(['wpctl', 'set-mute', '@DEFAULT_AUDIO_SOURCE@', 'toggle'])
        for requested, expected in [(-5, '0.000'), (42, '0.420'), (150, '1.000')]:
            backend.action({'action': 'mic-volume', 'percent': requested})
            command.assert_called_with(['wpctl', 'set-volume', '-l', '1', '@DEFAULT_AUDIO_SOURCE@', expected])

    @patch.object(backend, 'emit')
    @patch.object(backend, 'command', return_value='Volume: 0.42 [MUTED]')
    def test_osd_only_follows_successful_explicit_audio_operations(self, command, emit):
        request = {'action': 'mic-mute'}
        backend.handle(request)
        self.assertEqual(request, {})
        self.assertIn(('osd', {'kind': 'microphone', 'percent': 42, 'muted': True}), [c.args for c in emit.call_args_list])
        emit.reset_mock()
        command.side_effect = OSError('unavailable')
        backend.handle({'action': 'mic-mute'})
        self.assertFalse(any(call.args[0] == 'osd' for call in emit.call_args_list))

    def test_wallpaper_uses_machine_configuration_without_evaluating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            art = root / 'wallpaper with spaces.png'
            art.write_bytes(b'fixture')
            config = root / 'hyprpaper.conf'
            config.write_text(f'wallpaper {{\n path = {art}\n fit_mode = cover\n}}\n')
            with patch.dict(os.environ, ATELIER_WALLPAPER_CONFIG=str(config)):
                self.assertEqual(backend.wallpaper_path(), str(art))
                art.unlink()
                self.assertEqual(backend.wallpaper_path(), '')

    def test_native_agent_registration_loss_terminates_for_retry(self):
        child = MagicMock()
        child.poll.return_value = None
        child.wait.side_effect = [subprocess.TimeoutExpired('qs', 2)] * 5 + [0]
        with patch.object(polkit.subprocess, 'Popen', return_value=child) as popen, \
                patch.object(polkit, 'ready', return_value=False), patch('sys.stderr', io.StringIO()):
            polkit.run_agent()
        popen.assert_called_once_with([polkit.QS, '-p', polkit.AUTH, '--no-duplicate'], stdin=subprocess.DEVNULL)
        child.terminate.assert_called_once()

    def test_native_agent_crash_restarts_native_not_another_ui(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(polkit, 'RUNTIME', Path(directory)), \
                patch.object(polkit.signal, 'signal'), patch.object(polkit.time, 'sleep'), \
                patch.object(polkit, 'run_agent', side_effect=[None, SystemExit(0)]) as run:
            with self.assertRaises(SystemExit):
                polkit.supervise()
            self.assertEqual(run.call_count, 2)

    def test_registered_native_agent_is_not_terminated(self):
        child = MagicMock()
        child.poll.side_effect = [None, 0, 0]
        child.wait.side_effect = subprocess.TimeoutExpired('qs', 2)
        with patch.object(polkit.subprocess, 'Popen', return_value=child), \
                patch.object(polkit, 'ready', return_value=True):
            polkit.run_agent()
        child.terminate.assert_not_called()

    def test_hardware_controls_send_manual_osd_with_fake_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / 'bin'
            tools.mkdir()
            capture = root / 'captured.json'
            scripts = {
                'wpctl': '#!/usr/bin/python3\nimport sys\nif sys.argv[1]=="get-volume": print("Volume: 0.55")\n',
                'brightnessctl': '#!/usr/bin/python3\nimport sys\nif "set" not in sys.argv: print("test,backlight,30,30%,100")\n',
                'qs': '#!/usr/bin/python3\nimport json,os,sys\nopen(os.environ["CAPTURE"],"w").write(json.dumps(sys.argv[1:]))\n',
            }
            for name, text in scripts.items():
                path = tools / name
                path.write_text(text)
                path.chmod(0o755)
            env = dict(os.environ, PATH=f'{tools}:/usr/bin', XDG_RUNTIME_DIR=str(root), CAPTURE=str(capture), ATELIER_QS_BINARY='qs')
            helper = str(ROOT / 'hyprland-common/.local/bin/desktop-control')
            for action, kind, percent in [('volume-up', 'volume', '55'), ('mic-mute', 'microphone', '55'), ('brightness-down', 'brightness', '30')]:
                subprocess.run([helper, action], env=env, check=True)
                self.assertEqual(json.loads(capture.read_text())[-3:], [kind, percent, 'false'])
            bad = subprocess.run([helper, 'volume-up; bad'], env=env, capture_output=True)
            self.assertEqual(bad.returncode, 2)
