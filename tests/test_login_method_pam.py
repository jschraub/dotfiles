"""Exercise the real selector and PAM control flow in a private configuration.

No real password, fingerprint, faillock database, account or system PAM file is
used. Standard permit/deny modules stand in for credential verification only.
"""
import ctypes as C
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULES = Path('/usr/lib/security')


class Message(C.Structure):
    _fields_ = [('style', C.c_int), ('message', C.c_char_p)]


class Response(C.Structure):
    _fields_ = [('response', C.c_void_p), ('code', C.c_int)]


Conversation = C.CFUNCTYPE(C.c_int, C.c_int, C.POINTER(C.POINTER(Message)), C.POINTER(C.POINTER(Response)), C.c_void_p)


class Conv(C.Structure):
    _fields_ = [('conversation', Conversation), ('data', C.c_void_p)]


@unittest.skipUnless(shutil.which('cc') and (MODULES / 'pam_permit.so').exists(), 'requires Arch PAM modules and C compiler')
class LoginMethodPamTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.module = self.directory / 'pam_atelier_method.so'
        self.lid = self.directory / 'lid/state'
        source = self.directory / 'selector.c'
        original = (ROOT / 'auth-setup/pam-method/pam_atelier_method.c').read_text()
        source.write_text(original.replace('"/proc/acpi/button/lid/*/state"', '"' + str(self.lid) + '"'))
        subprocess.run(['cc', '-std=c11', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                        str(source), '-lpam', '-o', str(self.module)], check=True, capture_output=True)
        self.pam = C.CDLL('libpam.so.0')
        self.pam.pam_start_confdir.argtypes = [C.c_char_p, C.c_char_p, C.POINTER(Conv), C.c_char_p, C.POINTER(C.c_void_p)]
        self.pam.pam_authenticate.argtypes = [C.c_void_p, C.c_int]
        self.pam.pam_setcred.argtypes = [C.c_void_p, C.c_int]
        self.pam.pam_end.argtypes = [C.c_void_p, C.c_int]
        self.libc = C.CDLL(None)
        self.libc.calloc.argtypes = [C.c_size_t, C.c_size_t]
        self.libc.calloc.restype = C.c_void_p
        self.libc.strdup.argtypes = [C.c_char_p]
        self.libc.strdup.restype = C.c_void_p

    def authenticate(self, method, *, fingerprint=True, password=True, selector=True, preauth=True):
        text = (ROOT / 'auth-setup/pam/atelier-login').read_text()
        if not preauth:
            text = text.replace('pam_faillock.so preauth', str(MODULES / 'pam_deny.so'))
        for name in ('pam_shells.so', 'pam_faillock.so', 'pam_env.so'):
            text = text.replace(name, str(MODULES / 'pam_permit.so'))
        text = text.replace('pam_systemd_home.so', str(self.directory / 'missing-homed.so'))
        text = text.replace('pam_atelier_method.so', str(self.module if selector else self.directory / 'missing-selector.so'))
        text = text.replace('pam_fprintd.so', str(MODULES / ('pam_permit.so' if fingerprint else 'pam_deny.so')) if fingerprint is not None else str(self.directory / 'missing-fprintd.so'))
        text = text.replace('pam_unix.so', str(MODULES / ('pam_permit.so' if password else 'pam_deny.so')))
        (self.directory / 'test-login').write_text(text)
        prompts = []

        @Conversation
        def converse(count, messages, responses, data):
            array = C.cast(self.libc.calloc(count, C.sizeof(Response)), C.POINTER(Response))
            for index in range(count):
                message = messages[index].contents
                prompts.append((message.style, message.message.decode()))
                array[index].response = self.libc.strdup(method.encode())
            responses[0] = array
            return 0

        conv = Conv(converse, None)
        handle = C.c_void_p()
        self.assertEqual(self.pam.pam_start_confdir(b'test-login', b'fixture-account', C.byref(conv),
                                                  str(self.directory).encode(), C.byref(handle)), 0)
        try:
            result = self.pam.pam_authenticate(handle, 0)
            if result == 0:
                self.assertEqual(self.pam.pam_setcred(handle, 2), 0, 'greetd credential setup must follow the chosen branch too')
        finally:
            self.pam.pam_end(handle, 0)
        if selector:
            self.assertEqual(prompts, [(1, 'Atelier authentication method:')])
        return result

    def test_password_skips_fingerprint_including_missing_module(self):
        self.assertEqual(self.authenticate('password', fingerprint=False), 0)
        self.assertEqual(self.authenticate('password', fingerprint=None), 0)

    def test_fingerprint_does_not_require_password_verification(self):
        self.assertEqual(self.authenticate('fingerprint', password=False), 0)

    def test_failed_or_missing_fingerprint_does_not_fall_through_to_password(self):
        self.assertNotEqual(self.authenticate('fingerprint', fingerprint=False), 0)
        self.assertNotEqual(self.authenticate('fingerprint', fingerprint=None), 0)

    def test_closed_lid_enforces_password_branch_even_if_client_requests_fingerprint(self):
        self.lid.parent.mkdir()
        self.lid.write_text('state: closed\n')
        self.assertEqual(self.authenticate('fingerprint', fingerprint=False, password=True), 0)
        self.assertNotEqual(self.authenticate('fingerprint', fingerprint=True, password=False), 0)

    def test_invalid_or_missing_selector_cannot_authenticate(self):
        for method in ('', 'invalid', 'fingerprint\n', 'PASSWORD'):
            with self.subTest(method=method):
                self.assertNotEqual(self.authenticate(method), 0)
        self.assertNotEqual(self.authenticate('password', selector=False), 0)

    def test_password_failure_is_not_bypassed_by_a_successful_fingerprint_backend(self):
        self.assertNotEqual(self.authenticate('password', fingerprint=True, password=False), 0)

    def test_method_choice_does_not_override_required_pre_authentication_policy(self):
        self.assertNotEqual(self.authenticate('fingerprint', preauth=False), 0)
        self.assertNotEqual(self.authenticate('password', preauth=False), 0)
