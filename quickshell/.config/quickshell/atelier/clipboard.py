#!/usr/bin/env python3
"""Bounded RAM-only clipboard owner. Private pipes/socket; never logs contents."""
import base64
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid

MAX_TEXT = 256 * 1024
MAX_IMAGE = 8 * 1024 * 1024
MAX_BYTES = 16 * 1024 * 1024
MAX_ITEMS = 50
MAX_LINE = MAX_IMAGE * 4 // 3 + 4096
PNG = b'\x89PNG\r\n\x1a\n'


def parent_death(expected):
    # Process groups alone don't cover a crashed/killed Quickshell owner. Linux
    # propagates parent death through the helper and each wl-paste watcher.
    if expected <= 1:
        raise SystemExit(0)
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise OSError('Cannot bind clipboard process lifetime')
    if os.getppid() != expected:
        raise SystemExit(0)


def identify(kind, data):
    if kind == 'text':
        if not data or len(data) > MAX_TEXT or b'\0' in data:
            raise ValueError('Unsupported text')
        return {'mime': 'text/plain;charset=utf-8', 'text': data.decode('utf-8')}
    if kind == 'image':
        if not 33 <= len(data) <= MAX_IMAGE or data[:8] != PNG or data[12:16] != b'IHDR':
            raise ValueError('Unsupported image')
        width, height = struct.unpack('>II', data[16:24])
        if not width or not height or max(width, height) > 8192 or width * height > 16 * 1024 * 1024:
            raise ValueError('Image too large')
        return {'mime': 'image/png', 'width': width, 'height': height}
    raise ValueError('Unsupported clipboard type')


class History:
    def __init__(self, *, max_items=MAX_ITEMS, max_bytes=MAX_BYTES):
        self.entries = []
        self.paused = False
        self.epoch = 0
        self.max_items, self.max_bytes = max_items, max_bytes
        self.lock = threading.RLock()
        self.blocked = {}  # Brief tombstones reject delayed delete/clear echoes.
        self.echo = None

    def offer(self):
        with self.lock:
            return {'accept': not self.paused, 'epoch': self.epoch}

    def _dispose(self, entry):
        if 'fd' in entry:
            os.close(entry['fd'])

    def add(self, kind, data, epoch):
        with self.lock:
            if self.paused or epoch != self.epoch:
                return False
            metadata = identify(kind, data)
            digest = hashlib.sha256(kind.encode() + data).hexdigest()
            now = time.monotonic()
            self.blocked = {key: until for key, until in self.blocked.items() if until > now}
            if digest in self.blocked:
                return False
            if self.echo and self.echo[0] == digest and self.echo[1] > now:
                self.echo = None
                return False
            old = next((entry for entry in self.entries if entry['digest'] == digest), None)
            if old:
                self.entries.remove(old)
                self.entries.insert(0, old)
                return True
            if len(data) > self.max_bytes:
                return False
            entry = {'id': uuid.uuid4().hex, 'kind': kind, 'data': data, 'digest': digest, **metadata}
            if kind == 'image':
                # Anonymous memory, not a thumbnail/history file on disk. Qt
                # receives a /proc path, never a data URL that could enter logs.
                descriptor = os.memfd_create('atelier-clipboard', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
                try:
                    with os.fdopen(os.dup(descriptor), 'wb') as output:
                        output.write(data)
                    fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS,
                                fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
                except BaseException:
                    os.close(descriptor)
                    raise
                entry['fd'] = descriptor
            self.entries.insert(0, entry)
            while len(self.entries) > self.max_items or sum(len(item['data']) for item in self.entries) > self.max_bytes:
                self._dispose(self.entries.pop())
            return True

    def snapshot(self, query='', *, visible=True):
        with self.lock:
            rows = []
            if visible:
                needle = query.casefold()
                for entry in self.entries:
                    text = entry.get('text', '')
                    label = text if entry['kind'] == 'text' else f"PNG image {entry['width']}×{entry['height']}"
                    if needle not in label.casefold():
                        continue
                    row = {'id': entry['id'], 'kind': entry['kind'], 'size': len(entry['data']),
                           'label': label[:240], 'text': text[:16384], 'truncated': len(text) > 16384}
                    if entry['kind'] == 'image':
                        row.update(width=entry['width'], height=entry['height'],
                                   preview=f"file:///proc/{os.getpid()}/fd/{entry['fd']}")
                    rows.append(row)
            return {'items': rows, 'count': len(self.entries), 'paused': self.paused}

    def pause(self, value):
        with self.lock:
            if type(value) is not bool:
                raise ValueError('Invalid pause state')
            self.paused = value
            self.epoch += 1  # Reject reads admitted before pause/resume.

    def remove(self, identifier=None):
        with self.lock:
            self.epoch += 1
            removed = [entry for entry in self.entries if identifier is None or entry['id'] == identifier]
            for entry in removed:
                self.blocked[entry['digest']] = time.monotonic() + 5
                self.entries.remove(entry)
                self._dispose(entry)
            self.blocked = dict(list(self.blocked.items())[-MAX_ITEMS * 2:])

    def copy(self, identifier):
        with self.lock:
            entry = next((entry for entry in self.entries if entry['id'] == identifier), None)
            if not entry:
                raise ValueError('Clipboard item is no longer available')
            subprocess.run(['wl-copy', '--type', entry['mime']], input=entry['data'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4, check=True)
            self.echo = (entry['digest'], time.monotonic() + 5)
            self.entries.remove(entry)
            self.entries.insert(0, entry)


def capture(kind):
    # Inspect the source hint BEFORE reading or transferring any content.
    if os.environ.get('CLIPBOARD_STATE') != 'data':
        return
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(4)
            connection.connect(os.environ['ATELIER_CLIPBOARD_SOCKET'])
            stream = connection.makefile('rwb')
            stream.write(b'offer\n'); stream.flush()
            ticket = json.loads(stream.readline(1024))
            if not ticket.get('accept'):
                return
            limit = MAX_TEXT if kind == 'text' else MAX_IMAGE
            # A pipe may belong to a stalled app; never wait indefinitely.
            import select
            chunks, length, deadline = [], 0, time.monotonic() + 2
            while length <= limit:
                if not select.select([sys.stdin.buffer], [], [], max(0, deadline - time.monotonic()))[0]:
                    return
                block = os.read(sys.stdin.fileno(), min(65536, limit + 1 - length))
                if not block:
                    break
                chunks.append(block); length += len(block)
                if time.monotonic() >= deadline:
                    return
            data = b''.join(chunks)
            identify(kind, data)
            stream.write(json.dumps({'kind': kind, 'epoch': ticket['epoch'],
                                     'data': base64.b64encode(data).decode('ascii')}).encode() + b'\n')
            stream.flush()
    except (OSError, ValueError, KeyError, UnicodeError):
        pass  # Never print clipboard content, protocol bodies or tool stderr.


def serve():
    parent_death(os.getppid())
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    history = History()
    stop = threading.Event()
    output_lock = threading.Lock()
    state = {'visible': False, 'query': ''}
    watchers = []

    def emit(event='state', message=''):
        data = history.snapshot(state['query'], visible=state['visible'])
        data.update(ready=len(watchers) == 2 and all(child.poll() is None for child in watchers), message=message)
        with output_lock:
            try:
                print(json.dumps({'type': event, 'data': data}), flush=True)
            except BrokenPipeError:
                stop.set()

    def halt(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, halt)
    signal.signal(signal.SIGINT, halt)
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if not runtime:
        raise SystemExit('A Wayland runtime directory is required')
    scope = hashlib.sha256(os.environ.get('WAYLAND_DISPLAY', '').encode()).hexdigest()[:16]
    pause_file = Path(runtime) / f'atelier-clipboard-{scope}.paused'
    history.paused = pause_file.exists()
    with tempfile.TemporaryDirectory(prefix='atelier-clipboard-', dir=runtime) as directory:
        path = str(Path(directory) / 'capture.sock')
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(path); os.chmod(path, 0o600); server.listen(4); server.settimeout(.2)

            def receive_captures():
                while not stop.is_set():
                    try:
                        connection, _ = server.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        return
                    stream = None
                    try:
                        with connection:
                            connection.settimeout(4)
                            _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                            if uid != os.getuid():
                                continue
                            stream = connection.makefile('rwb')
                            if stream.readline(32) != b'offer\n':
                                continue
                            stream.write(json.dumps(history.offer()).encode() + b'\n'); stream.flush()
                            line = stream.readline(MAX_LINE + 1)
                            if len(line) > MAX_LINE:
                                continue
                            request = json.loads(line)
                            data = base64.b64decode(request['data'], validate=True)
                            if history.add(request['kind'], data, request['epoch']):
                                emit()
                    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
                        continue
                    finally:
                        if stream is not None:
                            try:
                                stream.close()
                            except OSError:
                                pass
                        # Do not retain the last raw/base64 payload in this
                        # long-lived thread's frame after history is cleared.
                        line = request = data = None

            thread = threading.Thread(target=receive_captures, daemon=True)
            thread.start()
            environment = dict(os.environ, ATELIER_CLIPBOARD_SOCKET=path, ATELIER_CLIPBOARD_PARENT=str(os.getpid()))
            specs = [('text', 'text'), ('image', 'image/png')]
            def start_watcher(kind, mime):
                return subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), 'watch', kind],
                                        env=environment, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            def watch_health():
                while not stop.wait(2):
                    changed = False
                    for index, child in enumerate(watchers):
                        if child.poll() is not None:
                            changed = True
                            try:
                                watchers[index] = start_watcher(*specs[index])
                            except OSError:
                                pass
                    if changed:
                        emit()
            monitor = None
            try:
                for kind, mime in specs:
                    watchers.append(start_watcher(kind, mime))
                monitor = threading.Thread(target=watch_health, daemon=True)
                monitor.start()
                emit()
                for line in sys.stdin:
                    try:
                        request = json.loads(line)
                        action = request['action']
                        if action == 'list':
                            state.update(visible=True, query=str(request.get('query', ''))[:512])
                        elif action == 'hide':
                            state.update(visible=False, query='')
                        elif action == 'pause':
                            paused = request['paused']
                            if type(paused) is not bool:
                                raise ValueError('Invalid pause state')
                            if paused:
                                history.pause(True)
                                fd = os.open(pause_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
                                with os.fdopen(fd, 'w') as flag:
                                    os.fchmod(flag.fileno(), 0o600)
                                    flag.write('paused\n')
                            else:
                                pause_file.unlink(missing_ok=True)
                                history.pause(False)
                        elif action == 'delete':
                            history.remove(str(request['id']))
                        elif action == 'clear':
                            history.remove()
                        elif action == 'copy':
                            history.copy(str(request['id']))
                            emit('copied')
                            continue
                        else:
                            raise ValueError('Unsupported clipboard action')
                        emit()
                    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                        emit(message='Clipboard action failed. The item may no longer be available.')
            finally:
                stop.set()
                if monitor:
                    monitor.join(timeout=5)
                for child in watchers:
                    try:
                        os.killpg(child.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                for child in watchers:
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL); child.wait()
                thread.join(timeout=5)
                history.remove()


if __name__ == '__main__':
    if sys.argv[1:] == ['serve']:
        serve()
    elif len(sys.argv) == 3 and sys.argv[1] == 'capture' and sys.argv[2] in ('text', 'image'):
        capture(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'watch' and sys.argv[2] in ('text', 'image'):
        parent_death(int(os.environ['ATELIER_CLIPBOARD_PARENT']))
        mime = 'text' if sys.argv[2] == 'text' else 'image/png'
        os.execvp('wl-paste', ['wl-paste', '--no-newline', '--type', mime, '--watch',
                              sys.executable, '-B', str(Path(__file__).resolve()), 'capture', sys.argv[2]])
    else:
        raise SystemExit('Usage: clipboard.py serve|capture text|capture image')
