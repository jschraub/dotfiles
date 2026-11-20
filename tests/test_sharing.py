"""Sharing tests use fake receivers, fake senders and private temporary sockets."""
import importlib.util
import json
import os
import shutil
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'quickshell/.config/quickshell/atelier/sharing.py'
spec = importlib.util.spec_from_file_location('atelier_sharing', SCRIPT)
sharing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sharing)


class SharingTest(unittest.TestCase):
    def test_nvenc_vaapi_and_software_launch_without_forcing_capture_gpu(self):
        for encoder in sharing.ENCODERS:
            with self.subTest(encoder=encoder), tempfile.TemporaryDirectory() as directory:
                controller = sharing.Sharing(directory)
                controller.encoder = encoder
                controller.socket.touch()
                child = MagicMock(); child.poll.return_value = None
                def spawn(command):
                    controller.socket.touch()
                    return child
                with patch.object(sharing.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'doubletake v0.6.0\n', '')), \
                        patch.object(controller, 'spawn', side_effect=spawn) as launch:
                    controller.start()
                command = launch.call_args.args[0]
                self.assertEqual(command[command.index('-hwaccel') + 1], encoder)
                self.assertEqual(command[command.index('-cred-backend') + 1], 'keyring')
                self.assertIn('-no-audio', command)
                self.assertNotIn('radeonsi', ' '.join(command))
                self.assertNotIn('-debug', command)
                self.assertNotIn('-code', command)

    def test_targets_must_be_explicit_discovered_local_receivers(self):
        controller = sharing.Sharing('/unused')
        with patch.object(controller, 'start'), patch.object(controller, 'rpc') as rpc:
            for target in ('192.0.2.20', '8.8.8.8', '127.0.0.1', '192.0.2.20; touch /bad', ''):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    controller.action(dict(action='connect', target=target))
            rpc.assert_not_called()

    def test_pairing_only_targets_pending_receiver_and_pins_device_identity(self):
        controller = sharing.Sharing('/unused')
        controller.devices = [dict(target='192.0.2.20', port=7000, identity='fixture-device')]
        controller.streams = [dict(target='192.0.2.20', state='pin_required')]
        request = dict(action='credential', target='192.0.2.20', value='fixture-secret')
        with patch.object(controller, 'start'), patch.object(controller, 'rpc') as rpc, patch.object(controller, 'refresh'):
            controller.action(request)
            self.assertNotIn('value', request)
            rpc.assert_called_once_with('connect', target='192.0.2.20', port=7000, device_id='fixture-device', pin='fixture-secret')
            controller.streams = []
            with self.assertRaises(ValueError):
                controller.action(dict(action='credential', target='192.0.2.20', value='fixture-secret'))

    def test_invalid_settings_and_live_reconfiguration_are_refused(self):
        controller = sharing.Sharing('/unused')
        for encoder, resolution, audio in [('cuda;bad', '1920x1080', False), ('auto', 'bad', False), ('auto', 'max', 'true')]:
            with self.assertRaises(ValueError):
                controller.action(dict(action='configure', encoder=encoder, resolution=resolution, audio=audio))
        controller.streams = [dict(target='192.0.2.20', state='streaming')]
        with self.assertRaises(ValueError):
            controller.action(dict(action='configure', encoder='none', resolution='1280x720', audio=False))

    def test_external_network_displays_is_not_adopted_or_killed(self):
        controller = sharing.Sharing('/unused')
        with patch.object(sharing.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '(true,)\n', '')), \
                patch.object(controller, 'spawn') as spawn:
            with self.assertRaises(ValueError):
                controller.action(dict(action='network'))
            spawn.assert_not_called()
            self.assertIsNone(controller.network)

    def test_stop_only_terminates_owned_children(self):
        controller = sharing.Sharing('/unused')
        daemon, network = MagicMock(), MagicMock()
        controller.daemon, controller.network = daemon, network
        with patch.object(controller, 'terminate') as terminate:
            controller.stop()
        self.assertEqual([call.args[0] for call in terminate.call_args_list], [daemon, network])
        self.assertIsNone(controller.daemon)
        self.assertIsNone(controller.network)

    def test_private_socket_transports_credentials_without_argv_or_error_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = sharing.Sharing(directory)
            received = []
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(str(controller.socket)); server.listen(1)
                def receive():
                    with server.accept()[0] as connection:
                        received.append(json.loads(connection.makefile('rb').readline()))
                        connection.sendall(b'{"ok":false,"error":"fixture-secret must not escape"}\n')
                thread = threading.Thread(target=receive); thread.start()
                controller.daemon = MagicMock(pid=os.getpid())
                controller.daemon.poll.return_value = None
                with self.assertRaises(ValueError) as error:
                    controller.rpc('connect', target='192.0.2.20', pin='fixture-secret')
                thread.join(timeout=3)
            self.assertEqual(received[0]['pin'], 'fixture-secret')
            self.assertNotIn('fixture-secret', str(error.exception))

    def test_socket_peer_must_be_the_owned_sender(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = sharing.Sharing(directory)
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(str(controller.socket)); server.listen(1)
                controller.daemon = MagicMock(pid=os.getpid() + 100000)
                controller.daemon.poll.return_value = None
                with self.assertRaisesRegex(ValueError, 'not owned'):
                    controller.rpc('status')

    def test_discovery_never_connects_to_first_device_automatically(self):
        controller = sharing.Sharing('/unused')
        response = dict(ok=True, devices=[dict(name='Living room', ip='192.0.2.20', port=7000, device_id='fixture')])
        with patch.object(controller, 'start'), patch.object(controller, 'rpc', return_value=response) as rpc:
            controller.action(dict(action='discover'))
        rpc.assert_called_once_with('devices')
        self.assertEqual(controller.devices[0]['identity'], 'fixture')

    def test_invalid_discovery_entries_do_not_hide_valid_receivers(self):
        controller = sharing.Sharing('/unused')
        response = dict(ok=True, devices=[dict(ip='8.8.8.8', port=7000, device_id='bad'),
                                         dict(name='Living room', ip='192.0.2.20', port=7000, device_id='fixture')])
        with patch.object(controller, 'rpc', return_value=response):
            controller.read_devices()
        self.assertEqual([device['target'] for device in controller.devices], ['192.0.2.20'])

    def test_child_does_not_inherit_pairing_or_debug_file_environment(self):
        controller = sharing.Sharing('/unused')
        with patch.dict(os.environ, DOUBLETAKE_CODE='fixture-secret', GST_DEBUG_FILE='/unused/log', LIBVA_DRIVER_NAME='nvidia'), \
                patch.object(sharing.subprocess, 'Popen') as popen:
            controller.spawn(['doubletake', '-daemonize'])
        env = popen.call_args.kwargs['env']
        self.assertNotIn('DOUBLETAKE_CODE', env)
        self.assertNotIn('GST_DEBUG_FILE', env)
        self.assertNotIn('LIBVA_DRIVER_NAME', env)
        self.assertEqual(popen.call_args.kwargs['stdout'], subprocess.DEVNULL)
        self.assertEqual(popen.call_args.kwargs['stderr'], subprocess.DEVNULL)

    def test_casting_is_opt_in_and_legacy_cast_has_no_amd_override(self):
        result = subprocess.run(['bash', '-c', 'source ./setup.sh; default_items; printf "\\n%s\\n" "${PKGS[casting]}"'], cwd=ROOT,
                                check=True, capture_output=True, text=True)
        self.assertNotIn('casting', result.stdout.splitlines())
        self.assertIn('libfdk-aac', result.stdout)
        self.assertNotIn('nvidia-utils', result.stdout, 'Never silently replace hardware-specific drivers')
        source = (SCRIPT.parent / 'backend.py').read_text()
        self.assertIn('"cast": ["gnome-network-displays"]', source)
        self.assertNotIn('LIBVA_DRIVER_NAME=radeonsi', source)


FAKE_SENDER = '''#!/usr/bin/python3
import json,os,signal,socket,sys
if "-version" in sys.argv:
    print("doubletake v0.6.0"); sys.exit(0)
open(os.environ["SENDER_ARGS"],"w").write(json.dumps(sys.argv[1:]))
path=sys.argv[sys.argv.index("-socket")+1]
server=socket.socket(socket.AF_UNIX); server.bind(path); os.chmod(path,0o700); server.listen()
streams=[]
signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
while True:
    connection,_=server.accept()
    with connection:
        request=json.loads(connection.makefile("rb").readline())
        command=request["cmd"]
        response={"ok":True,"state":"idle","streams":streams}
        if command=="devices":
            response["devices"]=[{"name":"Living room","ip":"192.0.2.20","port":7000,"device_id":"fixture-device"}]
        elif command=="connect":
            assert request["target"]=="192.0.2.20" and request["device_id"]=="fixture-device"
            state="streaming" if request.get("pin")=="fixture-secret" else "pin_required"
            streams=[{"device":"Living room","device_ip":"192.0.2.20","state":state,"credential_kind":"pin","encoder":"nvh264enc","hardware_encoded":True}]
        connection.sendall(json.dumps(response).encode()+b"\\n")
'''


class SharingProtocolTest(unittest.TestCase):
    def test_on_demand_pairing_status_and_owner_death_with_fake_sender(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'bin'; binary.mkdir()
            sender = binary / 'doubletake'; sender.write_text(FAKE_SENDER); sender.chmod(0o755)
            record = root / 'args.json'
            process = subprocess.Popen([sys.executable, '-B', str(SCRIPT), 'serve'], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                                       env=dict(os.environ, PATH=f'{binary}:/usr/bin', XDG_RUNTIME_DIR=str(root), SENDER_ARGS=str(record)))
            output = []
            try:
                def event():
                    self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'Sharing helper did not respond')
                    line = process.stdout.readline()
                    output.append(line)
                    return json.loads(line)
                def request(action, **fields):
                    process.stdin.write(json.dumps(dict(action=action, **fields)).encode() + b'\n')
                    return event()
                self.assertFalse(event()['daemonRunning'])
                self.assertFalse(record.exists(), 'Idle startup must not run sender/discovery/capture')
                state = request('discover')
                self.assertEqual(state['devices'][0]['name'], 'Living room')
                args = json.loads(record.read_text())
                self.assertIn('keyring', args)
                self.assertIn('auto', args)
                state = request('connect', target='192.0.2.20')
                self.assertEqual(state['streams'][0]['state'], 'pin_required')
                state = request('credential', target='192.0.2.20', value='fixture-secret')
                self.assertEqual(state['streams'][0]['state'], 'streaming')
                self.assertEqual(state['streams'][0]['encoder'], 'nvh264enc')
                self.assertNotIn(b'fixture-secret', b''.join(output))
                self.assertNotIn('fixture-secret', record.read_text())
                children = Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
                self.assertEqual(len(children), 1)
                process.kill(); process.wait(timeout=5)
                def alive(pid):
                    try:
                        return Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1][0] != 'Z'
                    except FileNotFoundError:
                        return False
                deadline = time.monotonic() + 5
                while any(alive(pid) for pid in children) and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertFalse(any(alive(pid) for pid in children), 'Sender must stop when its owner dies')
            finally:
                if process.poll() is None:
                    process.terminate(); process.wait(timeout=20)
                process.stdin.close(); process.stdout.close(); process.stderr.close()


@unittest.skipUnless(os.environ.get('ATELIER_GUI_TESTS') == '1', 'opt-in: fake screen-sharing panel')
class SharingUiTest(unittest.TestCase):
    def test_encoder_audio_pairing_refresh_and_stop_without_real_capture(self):
        qs = os.environ.get('ATELIER_QS_BINARY', shutil.which('qs') or 'qs')
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
            config = Path(directory) / 'atelier'
            shutil.copytree(SCRIPT.parent, config)
            shutil.copyfile(ROOT / 'tests/atelier-sharing.qml', config / 'test.qml')
            process = subprocess.Popen([qs, '-p', str(config / 'test.qml'), '--no-color'], stdout=log, stderr=subprocess.STDOUT)
            try:
                def ipc(*args):
                    result = subprocess.run([qs, 'ipc', '--pid', str(process.pid), 'call', 'test', *args],
                                            capture_output=True, text=True, timeout=3)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return result.stdout.strip()
                def state(): return json.loads(ipc('status'))
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    result = subprocess.run([qs, 'ipc', '--pid', str(process.pid), 'call', 'test', 'status'], capture_output=True, text=True)
                    if process.poll() is not None or (result.returncode == 0 and json.loads(result.stdout)['active']):
                        break
                    time.sleep(.05)
                self.assertIsNone(process.poll())
                self.assertEqual(ipc('click', 'sharing-encoder-nvenc'), 'true')
                self.assertEqual(state()['state']['encoder'], 'nvenc')
                self.assertEqual(ipc('click', 'sharing-audio'), 'true')
                self.assertTrue(state()['state']['audio'])
                self.assertEqual(ipc('click', 'sharing-discover'), 'true')
                self.assertEqual(ipc('click', 'sharing-device-192.0.2.20'), 'true')
                time.sleep(.05)
                self.assertEqual(state()['active'], 'sharing-credential')
                self.assertTrue(state()['protected'])
                ipc('secret')
                self.assertEqual(state()['length'], len('fixture-secret'))
                ipc('refresh')
                self.assertEqual(state()['length'], len('fixture-secret'), 'Status polling must not clear a partially entered code')
                self.assertEqual(ipc('click', 'sharing-submit'), 'true')
                self.assertTrue(state()['accepted'])
                self.assertEqual(state()['length'], 0)
                self.assertEqual(ipc('click', 'sharing-encoder-none'), 'false', 'Stop before changing a live encoder')
                self.assertEqual(ipc('click', 'sharing-stop'), 'true')
                self.assertEqual(state()['state']['streams'], [])
                self.assertEqual(ipc('click', 'sharing-network'), 'true')
                self.assertTrue(state()['state']['networkRunning'])
                self.assertEqual(ipc('click', 'sharing-stop'), 'true')
                self.assertFalse(state()['state']['networkRunning'])
                ipc('key', 'Escape')
                self.assertEqual(state()['panel'], '')
            finally:
                process.terminate(); process.wait(timeout=8)
                log.seek(0); output = log.read()
                self.assertNotIn('fixture-secret', output)
                for issue in ('ERROR', 'ReferenceError', 'TypeError', 'Unable to assign', 'Binding loop'):
                    self.assertNotIn(issue, output, output)
