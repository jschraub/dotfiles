"""Production greeter adapter against a private fake greetd socket; no real login."""
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
QS = os.environ.get('ATELIER_QS_BINARY', shutil.which('qs') or 'qs')


@unittest.skipUnless(os.environ.get('ATELIER_GUI_TESTS') == '1', 'opt-in: greeter adapter with a fake private server')
class GreetdMethodsProtocolTest(unittest.TestCase):
    def test_cancelled_scan_and_delayed_cancel_reply_cannot_launch_the_replacement(self):
        self.run_cancel_test(sleep=False)

    def test_sleep_acknowledges_only_cancel_reply_and_defers_new_auth_until_wake(self):
        self.run_cancel_test(sleep=True)

    def run_cancel_test(self, *, sleep):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
            root = Path(directory)
            shutil.copyfile(ROOT / 'quickshell/.config/quickshell/atelier/GreeterController.qml', root / 'GreeterController.qml')
            for name in ('GreetdTransport.qml', 'greetd_transport.py', 'greetd_protocol.py'):
                shutil.copyfile(ROOT / 'quickshell/.config/quickshell/atelier' / name, root / name)
            shutil.copyfile(ROOT / 'tests/atelier-greetd-methods.qml', root / 'test.qml')
            (root / 'qmldir').write_text('GreeterController 1.0 GreeterController.qml\nGreetdTransport 1.0 GreetdTransport.qml\n')
            address = str(root / 'greetd.sock')
            listener = socket.socket(socket.AF_UNIX)
            listener.bind(address)
            listener.listen(1)
            listener.settimeout(10)
            requests, failures = [], []
            scanning, launched = threading.Event(), threading.Event()
            cancelling, allow_cancel = threading.Event(), threading.Event()

            def serve():
                try:
                    with listener.accept()[0] as connection:
                        connection.settimeout(10)

                        def send(value):
                            payload = json.dumps(value).encode()
                            connection.sendall(struct.pack('=I', len(payload)) + payload)

                        def read(size):
                            value = b''
                            while len(value) < size:
                                chunk = connection.recv(size - len(value))
                                if not chunk:
                                    raise EOFError
                                value += chunk
                            return value

                        while True:
                            request = json.loads(read(struct.unpack('=I', read(4))[0]))
                            requests.append(request)
                            kind = request['type']
                            if kind == 'create_session':
                                send({'type': 'auth_message', 'auth_message_type': 'secret',
                                      'auth_message': 'Atelier authentication method:'})
                            elif kind == 'post_auth_message_response':
                                response = request.get('response')
                                if response == 'fingerprint':
                                    send({'type': 'auth_message', 'auth_message_type': 'info', 'auth_message': 'Touch sensor'})
                                elif response is None:
                                    scanning.set()  # Hold the response until cancellation, as a scan would.
                                elif response == 'password':
                                    send({'type': 'auth_message', 'auth_message_type': 'secret', 'auth_message': 'Password:'})
                                elif response == 'fixture-protocol-secret':
                                    send({'type': 'success'})
                                else:
                                    raise AssertionError('Unexpected fake response')
                            elif kind == 'cancel_session':
                                send({'type': 'error', 'error_type': 'auth_error', 'description': 'old scan cancelled'})
                                cancelling.set()
                                if sleep:
                                    if not allow_cancel.wait(5):
                                        raise AssertionError('Timed out waiting for test to release cancel reply')
                                else:
                                    time.sleep(.15)
                                send({'type': 'success'})  # Must be discarded, not treated as authentication.
                            elif kind == 'start_session':
                                launched.set()
                                return  # No session is ever executed by this fake server.
                except (EOFError, OSError) as error:
                    if not launched.is_set():
                        failures.append(error)
                except Exception as error:
                    failures.append(error)

            worker = threading.Thread(target=serve, daemon=True)
            worker.start()
            process = subprocess.Popen([QS, '-p', str(root / 'test.qml'), '--no-color'], stdout=log, stderr=subprocess.STDOUT,
                                       env=dict(os.environ, GREETD_SOCK=address))
            try:
                if not scanning.wait(8):
                    log.seek(0)
                    self.fail(log.read() + repr(failures) + repr([r['type'] for r in requests]))

                def ipc(method):
                    result = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', method],
                                            capture_output=True, text=True, timeout=3)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return result.stdout

                ipc('sleep' if sleep else 'password')
                if sleep:
                    self.assertTrue(cancelling.wait(5))
                    before = json.loads(ipc('status'))
                    self.assertEqual(before['sleepAcknowledgements'], [], 'An auth failure is not a cancel acknowledgement')
                    self.assertTrue(before['switching'])
                    allow_cancel.set()
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        after = json.loads(ipc('status'))
                        if after['sleepAcknowledgements']:
                            break
                        time.sleep(.02)
                    self.assertEqual(after['sleepAcknowledgements'], [1])
                    self.assertFalse(after['needsResponse'])
                    self.assertEqual(sum(r['type'] == 'create_session' for r in requests), 1,
                                     'Do not restart authentication while sleeping')
                    self.assertFalse(launched.is_set())
                    ipc('wake')
                deadline = time.monotonic() + 5
                state = {}
                while time.monotonic() < deadline:
                    state = json.loads(ipc('status'))
                    if state['method'] == 'password' and state['needsResponse']:
                        break
                    time.sleep(.02)
                self.assertTrue(state.get('needsResponse'), state)
                self.assertFalse(launched.is_set(), 'A cancel acknowledgement is not authentication success')
                ipc('respond')
                self.assertTrue(launched.wait(5))
                self.assertEqual([r['type'] for r in requests], [
                    'create_session', 'post_auth_message_response', 'post_auth_message_response',
                    'cancel_session', 'create_session', 'post_auth_message_response',
                    'post_auth_message_response', 'start_session'])
                self.assertEqual(requests[-1]['cmd'], ['/usr/bin/start-hyprland'])
                self.assertEqual(failures, [])
            finally:
                process.terminate()
                process.wait(timeout=5)
                listener.close()
                worker.join(timeout=2)
                log.seek(0)
                output = log.read()
                for issue in ('ERROR', 'ReferenceError', 'TypeError', 'fixture-protocol-secret', 'unexpected greetd response'):
                    self.assertNotIn(issue, output, output)
