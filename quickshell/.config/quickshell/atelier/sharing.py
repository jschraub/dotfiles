#!/usr/bin/env python3
"""Owned, on-demand screen sharing. Secrets use private pipes/socket, never argv."""
import ctypes
import ipaddress
import json
import os
from pathlib import Path
import resource
import re
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time

LIMIT = 64 * 1024
ENCODERS = ('auto', 'nvenc', 'vaapi', 'none')
RESOLUTIONS = ('1280x720', '1920x1080', 'max')
PLUGINS = ('pipewiresrc', 'pulsesrc', 'vapostproc', 'nvh264enc', 'vulkanh264enc', 'vah264enc', 'x264enc')


class SharingError(ValueError):
    """Only static, locally authored messages may cross the UI protocol."""


def parent_death(expected, death_signal=signal.SIGTERM):
    if expected <= 1:
        raise SystemExit(0)
    if ctypes.CDLL(None, use_errno=True).prctl(1, death_signal, 0, 0, 0) != 0:
        raise OSError('Cannot bind sharing process lifetime')
    if os.getppid() != expected:
        raise SystemExit(0)


def clean(value, limit=120):
    return ''.join(c for c in str(value) if c.isprintable())[:limit]


def address(value):
    value = str(value)
    ip = ipaddress.ip_address(value)
    if ip.is_global or ip.is_loopback or ip.is_multicast or ip.is_unspecified:
        raise SharingError('Choose a local-network receiver')
    return value


def capabilities():
    plugins = {}
    for name in PLUGINS:
        try:
            plugins[name] = subprocess.run(['gst-inspect-1.0', name], stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL, timeout=5).returncode == 0
        except (OSError, subprocess.SubprocessError):
            plugins[name] = False
    return plugins


def compatible_sender():
    try:
        result = subprocess.run(['doubletake', '-version'], capture_output=True, text=True, timeout=5, check=True)
        return bool(re.search(r'(?<![\w.])v?0\.6\.\d+\b', result.stdout))
    except (OSError, subprocess.SubprocessError):
        return False


class Sharing:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.socket = self.directory / 'airplay.sock'
        self.daemon = None
        self.network = None
        self.devices = []
        self.streams = []
        self.plugins = {}
        self.encoder, self.resolution, self.audio = 'auto', '1920x1080', False
        self.message = ''
        self.status_known = True
        self.lock = threading.RLock()

    def snapshot(self):
        with self.lock:
            return dict(airplayAvailable=bool(shutil.which('doubletake')),
                        networkAvailable=bool(shutil.which('gnome-network-displays')),
                        daemonRunning=self.daemon is not None and self.daemon.poll() is None,
                        networkRunning=self.network is not None and self.network.poll() is None,
                        statusKnown=self.status_known,
                        devices=self.devices, streams=self.streams, plugins=self.plugins,
                        encoder=self.encoder, resolution=self.resolution, audio=self.audio, message=self.message)

    def spawn(self, command):
        environment = dict(os.environ)
        # NVENC is selected separately. A session-wide NVIDIA VA decode driver
        # must not be forced onto AMD capture/postprocessing on hybrid laptops.
        for name in ('DOUBLETAKE_CODE', 'GST_DEBUG', 'GST_DEBUG_FILE', 'GST_DEBUG_DUMP_DOT_DIR', 'G_MESSAGES_DEBUG',
                     'LIBVA_DRIVER_NAME'):
            environment.pop(name, None)
        return subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), 'child',
                                 str(os.getpid()), *command], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, env=environment)

    @staticmethod
    def terminate(child):
        if child is None or child.poll() is not None:
            return
        try:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=5)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=2)

    def rpc(self, command, **fields):
        if not self.daemon or self.daemon.poll() is not None:
            raise SharingError('AirPlay is not running. Find devices first.')
        metadata = self.socket.lstat()
        if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise SharingError('AirPlay control socket ownership is invalid')
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(12)
            connection.connect(str(self.socket))
            pid, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != os.getuid() or pid != self.daemon.pid:
                raise SharingError('AirPlay control socket is not owned by this session')
            try:
                connection.sendall(json.dumps(dict(cmd=command, **fields)).encode() + b'\n')
            finally:
                fields.clear()
            with connection.makefile('rb') as stream:
                line = stream.readline(LIMIT + 1)
            if len(line) > LIMIT:
                raise SharingError('AirPlay returned an oversized response')
            response = json.loads(line)
            if not isinstance(response, dict) or response.get('ok') is not True:
                # Upstream error strings can contain receiver-controlled text.
                raise SharingError('AirPlay could not complete the request. Check the receiver, keyring, portal and encoder.')
            return response

    def start(self):
        if self.daemon and self.daemon.poll() is None:
            return
        if not compatible_sender():
            raise SharingError('This integration requires Doubletake 0.6.x. Run ./setup.sh casting.')
        self.socket.unlink(missing_ok=True)
        command = ['doubletake', '-daemonize', '-socket', str(self.socket), '-cred-backend', 'keyring',
                   '-hwaccel', self.encoder, '-resolution', self.resolution, '-fps', '30',
                   '-video-codec', 'h264', '-port-range', '60000-60010']
        command += ['-audio-source', 'monitor'] if self.audio else ['-no-audio']
        self.daemon = self.spawn(command)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if self.daemon.poll() is not None:
                raise SharingError('AirPlay could not start. Check dependencies and unlock your Secret Service keyring.')
            if self.socket.exists():
                return
            time.sleep(.05)
        self.terminate(self.daemon)
        raise SharingError('AirPlay startup timed out')

    def refresh(self):
        with self.lock:
            if self.network and self.network.poll() is not None:
                self.network = None
                self.message = 'Network Displays closed or delegated to another instance. Stop any external session in its own window.'
            if self.daemon:
                if self.daemon.poll() is not None:
                    self.daemon = None
                    self.devices, self.streams = [], []
                    self.message = 'AirPlay stopped. Sharing was not restarted automatically.'
                else:
                    response = self.rpc('status')
                    streams = []
                    for stream in (response.get('streams') or [])[:16]:
                        ip = address(stream['device_ip'])
                        state = stream.get('state')
                        if state not in ('connecting', 'streaming', 'pin_required'):
                            continue
                        streams.append(dict(target=ip, name=clean(stream.get('device') or ip), state=state,
                                                 credentialKind='password' if stream.get('credential_kind') == 'password' else 'pin',
                                                 encoder=clean(stream.get('encoder') or 'Negotiating', 40),
                                                 hardware=bool(stream.get('hardware_encoded'))))
                    self.streams = streams
                    self.status_known = True
                    if response.get('error'):
                        self.message = 'AirPlay reported a connection error. Stop and retry; no receiver error text was logged.'
                    self.read_devices()

    def read_devices(self):
        response = self.rpc('devices')
        devices = []
        for device in (response.get('devices') or [])[:64]:
            try:
                ip, port = address(device['ip']), device['port']
            except (ValueError, KeyError, TypeError):
                continue
            identity = clean(device.get('device_id') or '', 128)
            if not identity or type(port) is not int or not 1 <= port <= 65535:
                continue
            devices.append(dict(name=clean(device.get('name') or ip), target=ip, port=port, identity=identity))
        self.devices = devices

    def action(self, request):
        with self.lock:
            self.message = ''
            action = request.get('action')
            if action == 'check':
                self.plugins = capabilities()
            elif action == 'configure':
                encoder, resolution, audio = request.get('encoder'), request.get('resolution'), request.get('audio')
                if encoder not in ENCODERS or resolution not in RESOLUTIONS or type(audio) is not bool:
                    raise SharingError('Invalid AirPlay settings')
                if self.streams:
                    raise SharingError('Stop AirPlay before changing capture settings')
                self.terminate(self.daemon)
                self.daemon = None
                self.devices = []
                self.encoder, self.resolution, self.audio = encoder, resolution, audio
            elif action == 'discover':
                self.start()
                self.read_devices()
            elif action in ('connect', 'credential'):
                self.start()
                target = address(request.get('target'))
                device = next((device for device in self.devices if device['target'] == target), None)
                if not device:
                    raise SharingError('Find and choose a discovered AirPlay receiver')
                if self.streams and any(stream['target'] != target for stream in self.streams):
                    raise SharingError('Stop the current AirPlay session before selecting another receiver')
                fields = dict(target=target, port=device['port'], device_id=device['identity'])
                if action == 'credential':
                    if not any(stream['target'] == target and stream['state'] == 'pin_required' for stream in self.streams):
                        raise SharingError('This receiver is not waiting for a credential')
                    secret = request.pop('value', '')
                    if not isinstance(secret, str) or not 1 <= len(secret) <= 256:
                        raise SharingError('Enter the receiver PIN or password')
                    fields['pin'] = secret
                    secret = None
                try:
                    self.rpc('connect', **fields)
                finally:
                    fields.clear()
                self.refresh()
            elif action == 'network':
                if not self.network or self.network.poll() is not None:
                    owner = subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.DBus',
                                            '--object-path', '/org/freedesktop/DBus', '--method',
                                            'org.freedesktop.DBus.NameHasOwner', 'org.gnome.NetworkDisplays'],
                                           capture_output=True, text=True, timeout=3, check=True)
                    if 'true' in owner.stdout.lower():
                        raise SharingError('Network Displays is already running externally. Manage and stop that session in its own window.')
                    self.network = self.spawn(['gnome-network-displays'])
                self.message = 'Choose Miracast/Chromecast receivers and audio in Network Displays. Its open window does not prove a stream is active.'
            elif action == 'stop':
                self.stop()
            elif action == 'status':
                self.refresh()
            else:
                raise SharingError('Unknown screen-sharing action')

    def stop(self):
        with self.lock:
            self.terminate(self.daemon)
            self.terminate(self.network)
            self.daemon = self.network = None
            self.devices, self.streams = [], []
            self.message = 'Owned sharing processes stopped. External sharing applications are not controlled.'


def serve():
    parent_death(os.getppid())
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    runtime = Path(os.environ['XDG_RUNTIME_DIR'])
    metadata = runtime.stat()
    if metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        raise ValueError('A private user runtime directory is required')
    stop, output = threading.Event(), threading.Lock()
    with tempfile.TemporaryDirectory(prefix='atelier-sharing-', dir=runtime) as directory:
        sharing = Sharing(directory)

        def emit():
            state = sharing.snapshot()
            with output:
                print(json.dumps(state), flush=True)

        def monitor():
            while not stop.wait(1):
                try:
                    if sharing.daemon or sharing.network:
                        sharing.refresh()
                        emit()
                except (OSError, ValueError, KeyError, TypeError):
                    sharing.status_known = False
                    sharing.message = 'Sharing status is unavailable. Use Stop sharing; no automatic reconnection is attempted.'
                    try:
                        emit()
                    except BrokenPipeError:
                        return

        def halt(signum, frame):
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, halt)
        signal.signal(signal.SIGINT, halt)
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        try:
            emit()
            while True:
                line = sys.stdin.readline(4097)
                if not line:
                    break
                request = {}
                try:
                    if len(line) > 4096:
                        raise ValueError('Sharing request too large')
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        raise ValueError('Sharing request must be an object')
                    sharing.action(request)
                except SharingError as error:
                    sharing.message = str(error)
                except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                    sharing.message = 'Sharing action failed. Check setup, the receiver, portal, keyring and encoder.'
                finally:
                    if isinstance(request, dict):
                        request.clear()
                    request, line = None, None
                emit()
        finally:
            stop.set()
            thread.join(timeout=15)
            sharing.stop()


if __name__ == '__main__':
    if sys.argv[1:] == ['serve']:
        serve()
    elif sys.argv[1:] == ['--check']:
        print(json.dumps(dict(airplay=bool(shutil.which('doubletake')), network=bool(shutil.which('gnome-network-displays')),
                              airplayCompatible=compatible_sender(),
                              plugins=capabilities())))
    elif len(sys.argv) >= 4 and sys.argv[1] == 'child':
        # A wedged encoder must not keep streaming after its helper is killed.
        # Normal Stop still gives the owned process a graceful shutdown first.
        parent_death(int(sys.argv[2]), signal.SIGKILL)
        os.execvp(sys.argv[3], sys.argv[3:])
    else:
        raise SystemExit('Usage: sharing.py serve|--check')
