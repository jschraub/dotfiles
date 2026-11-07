"""Root-install staging, greeter-policy preservation, and public account metadata."""
import importlib.util
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load('access_installer', 'scripts/install_access.py')
identity = load('access_identity', 'quickshell/.config/quickshell/atelier/access_identity.py')


class AccessInstallTest(unittest.TestCase):
    def test_setup_does_not_reinstall_hyprlock_after_validated_native_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            environment = dict(os.environ, XDG_CONFIG_HOME=str(config))
            def packages():
                return subprocess.check_output(['bash', '-c', 'source ./setup.sh; hyprland_packages'],
                                               cwd=ROOT, env=environment, text=True).splitlines()
            self.assertIn('hyprlock', packages(), 'Unmigrated machines retain their existing locker')
            (config / 'dotfiles').mkdir()
            (config / 'dotfiles/lock-screen').write_text('atelier\n')
            self.assertNotIn('hyprlock', packages())
            self.assertIn('hypridle', packages())

    def test_verifier_has_private_runtime_without_desktop_session_environment(self):
        original = dict(os.environ)
        for privileged in (False, True):
            with self.subTest(privileged=privileged), tempfile.TemporaryDirectory() as directory, \
                    patch.dict(os.environ, WAYLAND_DISPLAY='live-wayland', DISPLAY=':99',
                               HYPRLAND_INSTANCE_SIGNATURE='live-session', DBUS_SESSION_BUS_ADDRESS='private-bus'), \
                    patch.object(installer.os, 'geteuid', return_value=0 if privileged else 1000), \
                    patch.object(installer.os, 'chown') as chown, \
                    patch.object(installer.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=977, pw_gid=977)):
                source = Path(directory) / 'original.lua'
                source.write_text('-- exact staged configuration\n')
                os.environ.pop('XDG_RUNTIME_DIR', None)  # sudo's actual failure mode
                def verify(command, *, env, check, **credentials):
                    runtime = Path(env['XDG_RUNTIME_DIR'])
                    self.assertTrue(runtime.is_dir())
                    self.assertEqual(runtime.stat().st_mode & 0o777, 0o700)
                    for key in ('WAYLAND_DISPLAY', 'DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE', 'DBUS_SESSION_BUS_ADDRESS'):
                        self.assertNotIn(key, env)
                    self.assertEqual(env['HOME'], str(runtime))
                    self.assertEqual(command, ['Hyprland', '--verify-config', '-c', str(runtime / 'hyprland.lua')])
                    self.assertEqual((runtime / 'hyprland.lua').read_bytes(), source.read_bytes())
                    self.assertEqual(credentials, {'user': 977, 'group': 977, 'extra_groups': []} if privileged else {})
                    self.assertTrue(check)
                with patch.object(installer.subprocess, 'run', side_effect=verify) as run:
                    installer.verify_config(source)
                    runtime = Path(run.call_args.kwargs['env']['XDG_RUNTIME_DIR'])
                self.assertEqual(chown.call_count, 2 if privileged else 0)
                self.assertFalse(runtime.exists())
        self.assertEqual(dict(os.environ), original)

    def test_password_pam_policy_is_identical_to_existing_hyprlock_policy(self):
        def statements(path):
            return [line.split() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
        self.assertEqual(statements(ROOT / 'auth-setup/pam/atelier-lock'),
                         statements(ROOT / 'pam-setup/etc/pam.d/hyprlock'))

    def test_greeter_reuses_all_existing_gpu_monitor_lid_policies(self):
        original = (ROOT / 'greetd-setup/etc/greetd/hyprland.lua').read_text()
        generated = installer.greeter_config(original)
        expected = original.replace('regreet; hyprctl', '/usr/bin/qs -p /etc/atelier/access/greeter.qml; hyprctl')
        self.assertEqual(generated, expected)

    def test_stage_does_not_change_live_login_or_lock_selection(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(installer.subprocess, 'run'):
            root = Path(directory)
            stage = installer.Installer(root, ROOT)
            stage.install(1000)
            self.assertFalse((root / 'etc/greetd/config.toml').exists())
            for name in installer.FILES:
                path = root / 'etc/atelier/access' / name
                self.assertTrue(path.is_file())
                self.assertFalse(path.is_symlink())
                self.assertEqual(path.stat().st_mode & 0o777, 0o644)
            self.assertEqual((root / 'etc/atelier').stat().st_mode & 0o777, 0o755)
            self.assertTrue((root / 'usr/share/atelier/access/avatars/1000.png').is_file())
            self.assertNotIn('pam_fprintd', (root / 'etc/pam.d/atelier-lock').read_text())
            self.assertNotIn('pam_unix', (root / 'etc/pam.d/atelier-fingerprint').read_text())

    def test_activation_preserves_vt_user_and_foreign_policy_is_rejected(self):
        source = '[terminal]\nvt = 3\n[default_session]\n# keep\ncommand = "' + installer.OLD + '"\nuser = "greeter"\n'
        updated = installer.activate_config(source)
        self.assertEqual(updated, source.replace(installer.OLD, installer.NEW))
        for foreign in (source.replace(installer.OLD, 'a-local-greeter'), source.replace('"greeter"', '"other"')):
            with self.assertRaises(ValueError):
                installer.activate_config(foreign)

    def test_installer_never_follows_a_greeter_writable_directory_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'etc').mkdir()
            (root / 'etc/atelier').symlink_to(root / 'user-owned')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                installer.Installer(root).directory('/etc/atelier/access')

    def test_lock_identity_uses_real_uid_not_environment_username(self):
        with patch.dict(os.environ, USER='not-the-current-account'):
            data = identity.identities('lock')
        self.assertEqual(data['users'][0]['user'], pwd.getpwuid(os.getuid()).pw_name)
        self.assertNotIn('password', str(data))
