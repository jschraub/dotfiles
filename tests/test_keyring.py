"""Migration boundaries with disposable homes; never uses the real keyring/TPM."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'keyring/.local/lib/atelier-keyring'
sys.path.insert(0, str(LIBRARY))
import credentials
import health
import migration
from paths import CREDENTIAL, Paths
sys.path.pop(0)


class KeyringTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.paths = Paths(self.root / 'config', self.root / 'data', self.root / 'state')
        self.paths.keyrings.mkdir(parents=True)
        (self.paths.keyrings / 'login.keyring').write_bytes(b'encrypted-fixture')
        self.paths.credential.parent.mkdir(parents=True)
        self.paths.credential.write_bytes(b'old-encrypted-credential')
        self.paths.credential.chmod(0o600)
        quiet = redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def activate(self, check=None):
        with patch.object(migration, 'preflight'), patch.object(migration, 'enabled', return_value=False), \
                patch.object(migration, 'systemctl') as ctl, patch.object(migration.subprocess, 'run'), \
                patch.object(migration, 'check', side_effect=check):
            migration.activate(self.paths)
            return ctl

    def test_activation_backs_up_keyrings_and_preserves_pkcs11(self):
        self.activate()
        record = json.loads((self.paths.state / 'migration.json').read_text())
        self.assertEqual((Path(record['backup']) / 'keyrings/login.keyring').read_bytes(), b'encrypted-fixture')
        self.assertEqual(self.paths.selector.read_text(), 'oo7\n')
        for path, template in migration.files(self.paths).items():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            if template:
                self.assertEqual(path.read_bytes(), (migration.TEMPLATES / template).read_bytes())
        self.assertIn('--components=pkcs11', (migration.TEMPLATES / 'gnome-pkcs11.conf').read_text())
        self.assertNotIn('--components=secrets', (migration.TEMPLATES / 'gnome-pkcs11.conf').read_text())
        self.assertEqual(self.paths.credential.read_bytes(), b'old-encrypted-credential')

    def test_failed_unlock_restores_previous_configuration(self):
        previous = self.paths.data / 'dbus-1/services/org.freedesktop.secrets.service'
        previous.parent.mkdir(parents=True)
        previous.write_bytes(b'previous provider configuration')
        with self.assertRaisesRegex(ValueError, 'still locked'):
            self.activate(ValueError('still locked'))
        self.assertEqual(previous.read_bytes(), b'previous provider configuration')
        self.assertFalse(self.paths.selector.exists())
        self.assertFalse((self.paths.state / 'migration.json').exists())
        self.assertTrue(list(self.paths.state.glob('migration-rolled-back-*')))
        self.assertEqual((self.paths.keyrings / 'login.keyring').read_bytes(), b'encrypted-fixture')

    def test_failed_tpm_precheck_never_stops_working_service(self):
        with patch.object(migration, 'preflight'), \
                patch.object(migration.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['systemd-creds'])), \
                patch.object(migration, 'systemctl') as ctl:
            with self.assertRaises(subprocess.CalledProcessError):
                migration.activate(self.paths)
            ctl.assert_not_called()
        self.assertFalse(self.paths.selector.exists())

    def test_refresh_does_not_collect_a_password_or_restart_services(self):
        self.activate()
        with patch.object(migration, 'systemctl') as ctl, patch.object(credentials.getpass, 'getpass') as password:
            migration.refresh(self.paths)
            password.assert_not_called()
            ctl.assert_called_once_with('daemon-reload')
        edited = self.paths.config / 'systemd/user/oo7-daemon.service.d/20-atelier-credentials.conf'
        edited.write_text('local override\n')
        with self.assertRaisesRegex(ValueError, 'Local keyring configuration differs'):
            migration.refresh(self.paths)
        self.assertEqual(edited.read_text(), 'local override\n')

    def test_rollback_preserves_post_migration_data(self):
        self.activate()
        migrated = self.paths.keyrings / 'v1/login.keyring'
        migrated.parent.mkdir()
        migrated.write_bytes(b'new-oo7-data')
        with patch.object(migration, 'systemctl'):
            migration.rollback(self.paths)
        self.assertEqual(migrated.read_bytes(), b'new-oo7-data')
        self.assertEqual(self.paths.credential.read_bytes(), b'old-encrypted-credential')
        self.assertFalse(self.paths.selector.exists())

    def test_symlinked_keyring_and_config_are_rejected(self):
        outside = self.root / 'outside'
        outside.write_text('keep')
        (self.paths.keyrings / 'foreign').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            migration.backup(self.paths)
        target = self.root / 'target'
        target.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            migration.write(target, b'replacement')
        self.assertEqual(outside.read_text(), 'keep')

    def test_provision_uses_private_bus_copy_and_explicit_tpm_policy(self):
        commands = []
        password = b'fixture-only-private-password'

        def run(command, **kwargs):
            commands.append((command, kwargs))
            self.assertNotIn(password.decode(), ' '.join(map(str, command)))
            self.assertNotIn('env', kwargs, 'Password must not be passed in the environment')
            if command[0] == 'dbus-run-session':
                copied_root = Path(command[-1])
                self.assertEqual((copied_root / 'data/keyrings/login.keyring').read_bytes(), b'encrypted-fixture')
                self.assertEqual(kwargs['stdout'], subprocess.DEVNULL)
            if command[:2] == ['systemd-creds', 'encrypt']:
                self.assertIn('--with-key=host+tpm2', command)
                self.assertIn('--user', command)
                self.assertIn('--tpm2-pcrs=7', command)
                Path(command[-1]).write_bytes(b'new-encrypted-credential')
            return subprocess.CompletedProcess(command, 0)

        with patch.object(credentials, 'preflight'), patch.object(credentials.sys.stdin, 'isatty', return_value=True), \
                patch.object(credentials.getpass, 'getpass', return_value=password.decode()), \
                patch.object(credentials.subprocess, 'run', side_effect=run):
            credentials.provision(self.paths)
        self.assertEqual(self.paths.credential.read_bytes(), b'new-encrypted-credential')
        self.assertEqual(self.paths.credential.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(commands), 3)
        self.assertEqual((self.paths.keyrings / 'login.keyring').read_bytes(), b'encrypted-fixture')

    def test_wrong_password_does_not_replace_existing_tpm_credential(self):
        with patch.object(credentials, 'preflight'), patch.object(credentials.sys.stdin, 'isatty', return_value=True), \
                patch.object(credentials.getpass, 'getpass', return_value='fixture-only-wrong-password'), \
                patch.object(credentials.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)) as run:
            with self.assertRaisesRegex(ValueError, 'could not decrypt'):
                credentials.provision(self.paths)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(self.paths.credential.read_bytes(), b'old-encrypted-credential')

    def test_status_rejects_a_locked_default_collection(self):
        with patch.object(health, 'bus', side_effect=[1234, '/collection/login', True]), \
                patch.object(health.Path, 'resolve', return_value=Path('/usr/lib/oo7-daemon')):
            with self.assertRaisesRegex(ValueError, 'still locked'):
                health.check()

    def test_status_understands_busctl_method_and_property_encodings(self):
        for payload, expected in (('{"type":"u","data":[1234]}', 1234),
                                  ('{"type":"b","data":false}', False)):
            with patch.object(health.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, payload)):
                self.assertEqual(health.bus('fixture-command'), expected)

    def test_setup_keeps_keyring_an_explicit_opt_in(self):
        output = subprocess.check_output(['bash', str(ROOT / 'setup.sh'), '--dry-run', 'all'], text=True)
        self.assertNotIn('oo7>=', output)
        explicit = subprocess.check_output(['bash', str(ROOT / 'setup.sh'), '--dry-run', 'keyring'], text=True)
        self.assertIn('oo7>=0.7.3', explicit)
        self.assertIn('setup-oo7.sh', explicit)


@unittest.skipUnless(os.environ.get('ATELIER_OO7_DAEMON') and os.environ.get('ATELIER_OO7_LEGACY_FIXTURE'),
                     'opt-in: real oo7 binary and upstream legacy fixture, private bus only')
class KeyringPrivateBusTest(unittest.TestCase):
    def test_real_daemon_accepts_fixture_password_and_rejects_wrong_password(self):
        # oo7 0.7.3 client/fixtures/legacy.keyring has the synthetic password "test".
        for password, expected in ((b'test', 0), (b'wrong-fixture-password', 1)):
            with self.subTest(correct=expected == 0), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                keyrings = root / 'data/keyrings'
                keyrings.mkdir(parents=True)
                shutil.copyfile(os.environ['ATELIER_OO7_LEGACY_FIXTURE'], keyrings / 'login.keyring')
                program = ('import sys; from pathlib import Path; '
                           'sys.path.insert(0, sys.argv[1]); import verify_password; '
                           'raise SystemExit(verify_password.verify(Path(sys.argv[2]), sys.argv[3]))')
                result = subprocess.run(['dbus-run-session', '--', sys.executable, '-B', '-c', program,
                                         str(LIBRARY), directory, os.environ['ATELIER_OO7_DAEMON']],
                                        input=password, capture_output=True, timeout=25)
                self.assertEqual(result.returncode, expected, result.stderr.decode())


@unittest.skipUnless(os.environ.get('ATELIER_TPM_TESTS') == '1', 'opt-in: synthetic TPM credential in a transient user service')
class KeyringTpmTest(unittest.TestCase):
    def test_user_service_receives_host_tpm2_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            credential = Path(directory) / CREDENTIAL
            subprocess.run(['systemd-creds', 'encrypt', '--user', '--with-key=host+tpm2', '--tpm2-pcrs=7',
                            f'--name={CREDENTIAL}', '-', str(credential)],
                           input=b'fixture-only-not-a-real-keyring-password', check=True, capture_output=True)
            program = ('import os; from pathlib import Path; '
                       f'value = (Path(os.environ["CREDENTIALS_DIRECTORY"]) / "{CREDENTIAL}").read_bytes(); '
                       'raise SystemExit(0 if value == b"fixture-only-not-a-real-keyring-password" else 1)')
            result = subprocess.run(['systemd-run', '--user', '--quiet', '--wait', '--collect', '--pipe',
                                     f'--unit=atelier-oo7-credential-test-{os.getpid()}',
                                     f'--property=LoadCredentialEncrypted={CREDENTIAL}:{credential}',
                                     '--property=PrivateUsers=yes', '--property=PrivateDevices=yes',
                                     sys.executable, '-B', '-c', program], capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
