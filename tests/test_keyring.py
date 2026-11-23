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
import keyring_session
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
                patch.object(migration, 'wait_for_ready', side_effect=check):
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
        self.assertTrue(list(self.paths.state.glob('migration-failed-*')))
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

    def test_failed_activation_preserves_oo7_data(self):
        migrated = self.paths.keyrings / 'v1/login.keyring'
        migrated.parent.mkdir()
        migrated.write_bytes(b'new-oo7-data')
        with self.assertRaisesRegex(ValueError, 'still locked'):
            self.activate(ValueError('still locked'))
        self.assertEqual(migrated.read_bytes(), b'new-oo7-data')
        self.assertEqual(self.paths.credential.read_bytes(), b'old-encrypted-credential')
        self.assertFalse(self.paths.selector.exists())

    def test_cli_does_not_offer_or_accept_gnome_rollback(self):
        helper = ROOT / 'keyring/.local/bin/desktop-keyring'
        help_text = subprocess.check_output([sys.executable, str(helper), '--help'], text=True)
        self.assertNotIn('rollback', help_text)
        result = subprocess.run([sys.executable, str(helper), 'rollback'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('invalid choice', result.stderr)

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

    def test_readiness_retries_until_unlocked(self):
        with patch.object(health, 'check', side_effect=[ValueError('locked'), None]) as probe, \
                patch.object(health.time, 'sleep') as sleep:
            health.wait_for_ready()
        self.assertEqual(probe.call_count, 2)
        sleep.assert_called_once()

    def test_readiness_deadline_does_not_accept_a_locked_collection(self):
        with patch.object(health.time, 'monotonic', side_effect=[0, 0, 15, 15]), \
                patch.object(health, 'check', side_effect=ValueError('still locked')) as probe, \
                patch.object(health.time, 'sleep'):
            with self.assertRaisesRegex(ValueError, 'still locked'):
                health.wait_for_ready()
        self.assertEqual(probe.call_count, 1)

    def test_selected_provider_failure_warns_without_fallback_or_reprovisioning(self):
        self.paths.selector.parent.mkdir(parents=True)
        self.paths.selector.write_text('oo7\n')
        with patch.object(keyring_session.subprocess, 'run') as run, \
                patch.object(keyring_session, 'wait_for_ready', side_effect=ValueError('locked')), \
                patch.object(keyring_session, 'warn') as warn, \
                patch.object(credentials, 'provision') as provision:
            with self.assertRaisesRegex(ValueError, 'desktop login is unaffected'):
                keyring_session.start(self.paths)
        warn.assert_called_once()
        provision.assert_not_called()
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('--components=secrets,pkcs11', run.call_args.args[0])
        self.assertEqual(self.paths.selector.read_text(), 'oo7\n')

    def test_healthy_start_does_not_warn(self):
        self.paths.selector.parent.mkdir(parents=True)
        self.paths.selector.write_text('oo7\n')
        with patch.object(keyring_session.subprocess, 'run'), \
                patch.object(keyring_session, 'wait_for_ready') as ready, \
                patch.object(keyring_session, 'warn') as warn:
            keyring_session.start(self.paths)
        ready.assert_called_once()
        warn.assert_not_called()

    def test_service_failure_warns_without_trying_another_provider(self):
        self.paths.selector.parent.mkdir(parents=True)
        self.paths.selector.write_text('oo7\n')
        with patch.object(keyring_session.subprocess, 'run',
                          side_effect=subprocess.CalledProcessError(1, ['systemctl'])) as run, \
                patch.object(keyring_session, 'wait_for_ready') as ready, \
                patch.object(keyring_session, 'warn') as warn:
            with self.assertRaisesRegex(ValueError, 'desktop login is unaffected'):
                keyring_session.start(self.paths)
        self.assertEqual(run.call_count, 1)
        ready.assert_not_called()
        warn.assert_called_once()

    def test_unselected_start_retains_the_previous_provider(self):
        with patch.object(keyring_session.subprocess, 'run') as run, \
                patch.object(keyring_session, 'wait_for_ready') as ready, \
                patch.object(keyring_session, 'warn') as warn:
            keyring_session.start(self.paths)
        run.assert_called_once_with(
            ['gnome-keyring-daemon', '--start', '--components=secrets,pkcs11'], check=True)
        ready.assert_not_called()
        warn.assert_not_called()

    def test_readiness_retries_bus_timeouts(self):
        with patch.object(health, 'check', side_effect=[
                subprocess.TimeoutExpired('busctl', 1), None]) as probe, \
                patch.object(health.time, 'sleep'):
            health.wait_for_ready()
        self.assertEqual(probe.call_count, 2)

    def test_warning_waits_for_notification_owner(self):
        with patch.object(keyring_session.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], 0, 'b false\n'),
                subprocess.CompletedProcess([], 0, 'b true\n'),
                subprocess.CompletedProcess([], 0)]) as run, \
                patch.object(keyring_session.time, 'sleep'), \
                patch.object(keyring_session.sys, 'stderr', io.StringIO()):
            keyring_session.warn()
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args.args[0][0], 'notify-send')

    def test_warning_timeout_keeps_diagnostic_and_does_not_activate_a_provider(self):
        with patch.object(keyring_session.time, 'monotonic', side_effect=[0, 11]), \
                patch.object(keyring_session.subprocess, 'run') as run, \
                patch.object(keyring_session.sys, 'stderr', io.StringIO()) as stderr:
            keyring_session.warn()
        run.assert_not_called()
        self.assertIn('desktop-keyring status', stderr.getvalue())

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
