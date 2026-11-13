"""RAM history tests. Fixtures only; never reads or writes the real clipboard."""
import base64
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'quickshell/.config/quickshell/atelier/clipboard.py'
spec = importlib.util.spec_from_file_location('atelier_clipboard', SCRIPT)
clipboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clipboard)


def png():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return clipboard.PNG + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + \
        chunk(b'IDAT', zlib.compress(b'\x00\x20\x20\x20')) + chunk(b'IEND', b'')


class HistoryTest(unittest.TestCase):
    def test_bounds_deduplication_and_search(self):
        history = clipboard.History(max_items=2, max_bytes=20)
        history.add('text', b'first', 0)
        identifier = history.entries[0]['id']
        history.add('text', b'Other', 0)
        history.add('text', b'first', 0)
        self.assertEqual(history.entries[0]['id'], identifier)
        self.assertEqual(len(history.entries), 2)
        self.assertEqual(history.snapshot('OTHER')['items'][0]['text'], 'Other')
        history.add('text', b'third', 0)
        self.assertEqual([item['text'] for item in history.snapshot()['items']], ['third', 'first'])
        self.assertEqual(history.snapshot(visible=False)['items'], [])
        history.add('text', b'123456789012345', 0)
        self.assertLessEqual(sum(len(item['data']) for item in history.entries), 20)

    def test_pause_and_clear_reject_inflight_captures(self):
        history = clipboard.History()
        ticket = history.offer()
        history.pause(True)
        self.assertFalse(history.offer()['accept'])
        self.assertFalse(history.add('text', b'private', ticket['epoch']))
        history.pause(False)
        ticket = history.offer()
        history.add('text', b'first', ticket['epoch'])
        history.remove()
        self.assertFalse(history.add('text', b'late', ticket['epoch']))
        self.assertFalse(history.add('text', b'first', history.epoch))
        self.assertEqual(history.snapshot()['count'], 0)

    def test_sensitive_unknown_and_empty_states_do_not_read_or_connect(self):
        for state in ('sensitive', 'nil', 'clear', 'unknown', ''):
            with self.subTest(state=state), patch.dict(os.environ, CLIPBOARD_STATE=state), \
                    patch.object(clipboard.socket, 'socket') as socket, patch.object(sys, 'stdin') as stdin:
                clipboard.capture('text')
                socket.assert_not_called()
                stdin.fileno.assert_not_called()

    def test_images_are_sealed_anonymous_memory_and_closed_on_remove(self):
        history = clipboard.History()
        data = png()
        history.add('image', data, 0)
        descriptor = history.entries[0]['fd']
        preview = history.snapshot()['items'][0]['preview']
        self.assertEqual(Path(preview.removeprefix('file://')).read_bytes(), data)
        with self.assertRaises(OSError) as error:
            os.write(descriptor, b'change')
        self.assertEqual(error.exception.errno, errno.EPERM)
        history.remove(history.entries[0]['id'])
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_invalid_oversized_and_binary_content_is_rejected(self):
        for kind, data in [('text', b'\0'), ('text', b'\xff'), ('text', b'x' * (clipboard.MAX_TEXT + 1)),
                           ('image', b'not an image'), ('image', png()[:16] + struct.pack('>II', 100000, 100000) + png()[24:])]:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                clipboard.identify(kind, data)

    def test_copy_is_stdin_only_exact_bytes_and_does_not_execute_text(self):
        history = clipboard.History()
        text = b'$(touch not-a-command)\nline two\n'
        history.add('text', text, 0)
        with patch.object(clipboard.subprocess, 'run') as run:
            history.copy(history.entries[0]['id'])
        self.assertEqual(run.call_args.args[0], ['wl-copy', '--type', 'text/plain;charset=utf-8'])
        self.assertEqual(run.call_args.kwargs['input'], text)
        self.assertNotIn(text.decode(), str(run.call_args.args))
        self.assertFalse(history.add('text', text, 0), 'Own copy echo must not duplicate history')

    def test_truncation_metadata_does_not_change_original_unicode_bytes(self):
        history = clipboard.History()
        text = ('λ🙂\n' * 7000).encode()
        history.add('text', text, 0)
        row = history.snapshot()['items'][0]
        self.assertTrue(row['labelTruncated'])
        self.assertTrue(row['truncated'])
        self.assertEqual(row['characters'], 21000)
        self.assertEqual(row['previewCharacters'], 16384)
        self.assertEqual(row['text'], text.decode()[:16384])
        with patch.object(clipboard.subprocess, 'run') as run:
            history.copy(row['id'])
        self.assertEqual(run.call_args.kwargs['input'], text)

    def test_optional_expiry_disposes_images_and_rejects_inflight_offers(self):
        now = [1000.0]
        history = clipboard.History(clock=lambda: now[0])
        history.add('image', png(), 0)
        descriptor = history.entries[0]['fd']
        now[0] += 10000
        self.assertFalse(history.expire(), 'Default retention must remain unchanged')
        ticket = history.offer()
        history.set_expiry(300)
        self.assertEqual(history.snapshot()['count'], 0)
        self.assertEqual(history.snapshot()['expirySeconds'], 300)
        self.assertFalse(history.add('text', b'stale read', ticket['epoch']))
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_expiry_is_enforced_on_copy_even_when_paused_and_does_not_write_clipboard(self):
        now = [0.0]
        history = clipboard.History(clock=lambda: now[0])
        history.set_expiry(300)
        history.add('text', b'fixture', 0)
        identifier = history.entries[0]['id']
        history.pause(True)
        now[0] = 300
        with patch.object(clipboard.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                history.copy(identifier)
            run.assert_not_called()
        self.assertEqual(history.snapshot(visible=False)['count'], 0)

    def test_external_recapture_refreshes_expiry_but_picker_copy_does_not(self):
        now = [0.0]
        history = clipboard.History(clock=lambda: now[0])
        history.set_expiry(300)
        history.add('text', b'fixture', 0)
        now[0] = 200
        history.add('text', b'fixture', 0)
        now[0] = 350
        identifier = history.snapshot()['items'][0]['id']
        with patch.object(clipboard.subprocess, 'run'):
            history.copy(identifier)
        now[0] = 500
        self.assertTrue(history.expire())
        self.assertEqual(history.snapshot()['count'], 0)

    def test_disabling_expiry_and_invalid_options(self):
        now = [0.0]
        history = clipboard.History(clock=lambda: now[0])
        history.set_expiry(300)
        history.add('text', b'fixture', 0)
        history.set_expiry(0)
        now[0] = 10000
        self.assertEqual(history.snapshot()['count'], 1)
        for value in (True, 1, -1, 86400, '300', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                history.set_expiry(value)
        self.assertEqual(history.expiry_seconds, 0)


class ClipboardProtocolTest(unittest.TestCase):
    def test_expiry_notifies_hidden_ui_without_new_clipboard_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'bin'; binary.mkdir()
            watcher = binary / 'wl-paste'
            watcher.write_text('#!/usr/bin/python3\nimport signal\nsignal.pause()\n')
            watcher.chmod(0o755)
            env = dict(os.environ, PATH=f'{binary}:/usr/bin', XDG_RUNTIME_DIR=str(root))
            # Accelerate only the injected history clock, not timers or the
            # production expiry options. Exercise the actual idle monitor.
            code = ('import importlib.util,sys,time; '
                    'spec=importlib.util.spec_from_file_location("fixture_clipboard",sys.argv[1]); '
                    'm=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); '
                    'History=m.History; m.History=lambda:History(clock=lambda:time.monotonic()*300); m.serve()')
            process = subprocess.Popen([sys.executable, '-B', '-c', code, str(SCRIPT)], env=env,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                def event():
                    self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'Missing expiry event')
                    return json.loads(process.stdout.readline())['data']
                self.assertTrue(event()['ready'])
                process.stdin.write(b'{"action":"expiry","seconds":300}\n'); process.stdin.flush()
                self.assertEqual(event()['expirySeconds'], 300)
                socket = next(root.glob('atelier-clipboard-*/capture.sock'))
                subprocess.run([sys.executable, '-B', str(SCRIPT), 'capture', 'text'],
                               env=dict(env, ATELIER_CLIPBOARD_SOCKET=str(socket), CLIPBOARD_STATE='data'),
                               input=b'expiring fixture', check=True, timeout=5)
                self.assertEqual(event()['count'], 1)
                expired = event()
                self.assertEqual(expired['count'], 0)
                self.assertEqual(expired['items'], [], 'Hidden UI must not receive payloads')
            finally:
                process.stdin.close(); process.wait(timeout=10)
                self.assertEqual(process.returncode, 0)
                self.assertEqual(process.stderr.read(), b'')
                process.stdout.close(); process.stderr.close()

    def test_private_capture_pause_copy_and_shutdown_with_fake_wl_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'bin'; binary.mkdir()
            watcher = binary / 'wl-paste'
            watcher.write_text('#!/usr/bin/python3\nimport signal\nsignal.pause()\n')
            watcher.chmod(0o755)
            copier = binary / 'wl-copy'
            copier.write_text('#!/usr/bin/python3\nimport os,sys\nopen(os.environ["COPY_FILE"],"wb").write(sys.stdin.buffer.read())\n')
            copier.chmod(0o755)
            env = dict(os.environ, PATH=f'{binary}:/usr/bin', XDG_RUNTIME_DIR=str(root), COPY_FILE=str(root / 'copied'))
            scope = hashlib.sha256(env.get('WAYLAND_DISPLAY', '').encode()).hexdigest()[:16]
            pause_file = root / f'atelier-clipboard-{scope}.paused'
            pause_file.write_text('paused\n')  # A prior helper was paused before it restarted.
            expiry_file = root / f'atelier-clipboard-{scope}.expiry'
            expiry_file.write_text('300\n')
            process = subprocess.Popen([sys.executable, '-B', str(SCRIPT), 'serve'], env=env,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                def event():
                    self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'Clipboard service did not respond')
                    return json.loads(process.stdout.readline())
                def request(action, **fields):
                    process.stdin.write(json.dumps(dict(action=action, **fields)).encode() + b'\n')
                    process.stdin.flush()
                    return event()
                initial = event()['data']
                self.assertTrue(initial['ready'])
                self.assertTrue(initial['paused'], 'Restart must honor the session pause flag before capturing')
                self.assertEqual(initial['expirySeconds'], 300)
                self.assertEqual(request('expiry', seconds=1800)['data']['expirySeconds'], 1800)
                self.assertEqual(expiry_file.stat().st_mode & 0o777, 0o600)
                self.assertEqual(expiry_file.read_text(), '1800\n')
                self.assertFalse(request('pause', paused=False)['data']['paused'])
                socket = next(root.glob('atelier-clipboard-*/capture.sock'))
                self.assertEqual(socket.stat().st_mode & 0o777, 0o600)
                payload = b'fixture-only clipboard\nwith newline\n'
                capture_env = dict(env, ATELIER_CLIPBOARD_SOCKET=str(socket), CLIPBOARD_STATE='data')
                subprocess.run([sys.executable, '-B', str(SCRIPT), 'capture', 'text'], env=capture_env,
                               input=payload, check=True, timeout=5)
                captured = event()['data']
                self.assertEqual(captured['count'], 1)
                self.assertEqual(captured['items'], [], 'Hidden panel must not receive clipboard payloads')
                rows = request('list')['data']['items']
                self.assertEqual(rows[0]['text'].encode(), payload)
                copied = request('copy', id=rows[0]['id'])
                self.assertEqual(copied['type'], 'copied')
                self.assertEqual((root / 'copied').read_bytes(), payload)
                self.assertTrue(request('pause', paused=True)['data']['paused'])
                self.assertEqual(pause_file.stat().st_mode & 0o777, 0o600)
                subprocess.run([sys.executable, '-B', str(SCRIPT), 'capture', 'text'], env=capture_env,
                               input=b'never retain this fixture', check=True, timeout=5)
                self.assertEqual(request('list')['data']['count'], 1)
                self.assertFalse(request('pause', paused=False)['data']['paused'])
                self.assertEqual(request('clear')['data']['count'], 0)
                self.assertEqual(request('hide')['data']['items'], [])
            finally:
                process.stdin.close()
                process.wait(timeout=10)
                self.assertEqual(process.returncode, 0)
                self.assertEqual(process.stderr.read(), b'')
                process.stdout.close(); process.stderr.close()
            self.assertEqual([path for path in root.glob('atelier-clipboard-*') if path.is_dir()], [], 'Private sockets must be retired on shutdown')
            self.assertEqual(expiry_file.read_text(), '1800\n', 'Only content-free expiry metadata survives')

    def test_watchers_do_not_survive_a_killed_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'bin'; binary.mkdir()
            watcher = binary / 'wl-paste'
            watcher.write_text('#!/usr/bin/python3\nimport signal\nsignal.pause()\n')
            watcher.chmod(0o755)
            process = subprocess.Popen([sys.executable, '-B', str(SCRIPT), 'serve'],
                                       env=dict(os.environ, PATH=f'{binary}:/usr/bin', XDG_RUNTIME_DIR=str(root)),
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            try:
                self.assertTrue(select.select([process.stdout], [], [], 5)[0])
                self.assertTrue(json.loads(process.stdout.readline())['data']['ready'])
                children = Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
                self.assertEqual(len(children), 2)
                process.kill(); process.wait(timeout=5)
                def alive(pid):
                    try:
                        return Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1][0] != 'Z'
                    except FileNotFoundError:
                        return False
                deadline = time.monotonic() + 5
                while any(alive(pid) for pid in children) and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertFalse(any(alive(pid) for pid in children), 'No background capture after owner death')
            finally:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=5)
                process.stdin.close(); process.stdout.close()
