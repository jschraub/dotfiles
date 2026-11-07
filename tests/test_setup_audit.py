"""Read-only audit checks with isolated files and mocked system queries."""
from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_setup', ROOT / 'scripts/check_setup.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SetupAuditTest(unittest.TestCase):
    def test_theme_audit_detects_missing_browser_hook_without_runtime_writes(self):
        spec = importlib.util.spec_from_file_location('apply_theme_for_audit', ROOT / 'scripts/apply_theme.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        base = self.home / '.config/zen'
        profile = base / 'test.default'
        profile.mkdir(parents=True)
        (base / 'profiles.ini').write_text('[Profile0]\nPath=test.default\nIsRelative=1\n')
        installer.apply(self.home)
        pointer = self.home / '.local/share/icons/Bibata-Modern-Amber/cursors/left_ptr'
        pointer.parent.mkdir(parents=True)
        pointer.write_bytes(b'Xcur-fixture')
        audit = module.Audit(root=ROOT, home=self.home)
        with patch.object(audit, 'value'), patch.object(module.subprocess, 'run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = 'accent-color\n'
            audit.theme()
        self.assertEqual(audit.counts['DRIFT'], 0)
        (profile / 'chrome/userChrome.css').write_text('/* lost import */\n')
        audit = module.Audit(root=ROOT, home=self.home)
        with patch.object(audit, 'value'), patch.object(module.subprocess, 'run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = 'accent-color\n'
            audit.theme()
        self.assertEqual(audit.counts['DRIFT'], 1)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'repo/fish/.config/fish/config.fish'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('# intended config\n')
        self.home = self.root / 'home'
        self.target = self.home / '.config/fish/config.fish'
        self.target.parent.mkdir(parents=True)
        self.audit = module.Audit(root=self.root / 'repo', home=self.home)
        self.output = io.StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def test_matching_link_and_directory_fold(self):
        self.target.symlink_to(self.source)
        self.audit.stow('fish')
        self.assertEqual(self.audit.counts, {'OK': 1})
        self.target.unlink()
        self.target.parent.rmdir()
        self.target.parent.symlink_to(self.source.parent, target_is_directory=True)
        self.audit.stow('fish')
        self.assertEqual(self.audit.counts, {'OK': 2})

    def test_independent_copy_is_drift_even_with_matching_content(self):
        self.target.write_bytes(self.source.read_bytes())
        self.audit.file(self.source, self.target, linked=True)
        self.assertEqual(self.audit.counts, {'DRIFT': 1})
        self.assertIn('not linked', self.output.getvalue())

    def test_copied_system_file_and_permissions(self):
        self.target.write_bytes(self.source.read_bytes())
        self.target.chmod(0o640)
        self.audit.file(self.source, self.target, mode=0o640, uid=os.getuid())
        self.audit.file(self.source, self.target, mode=0o644)
        self.assertEqual(self.audit.counts, {'OK': 1, 'DRIFT': 1})

    def test_different_content_is_not_printed(self):
        self.target.write_text('sensitive local value\n')
        self.audit.file(self.source, self.target)
        self.assertEqual(self.audit.counts, {'DRIFT': 1})
        self.assertNotIn('sensitive local value', self.output.getvalue())

    def test_missing_and_broken_targets(self):
        self.audit.file(self.source, self.target)
        self.target.symlink_to(self.root / 'missing')
        self.audit.file(self.source, self.target)
        self.assertEqual(self.audit.counts, {'DRIFT': 2})

    def test_unreadable_target_is_unknown_not_missing(self):
        original = Path.stat

        def stat(path, *args, **kwargs):
            if path == self.target:
                raise PermissionError('denied')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'stat', stat):
            self.audit.file(self.source, self.target)
        self.assertEqual(self.audit.counts, {'UNKNOWN': 1})

    def test_stow_ignores_extra_local_files(self):
        self.target.symlink_to(self.source)
        (self.target.parent / 'personal.fish').write_text('untouched\n')
        self.audit.stow('fish')
        self.assertEqual(self.audit.counts, {'OK': 1})
        self.assertEqual((self.target.parent / 'personal.fish').read_text(), 'untouched\n')

    def test_registry_can_be_read_without_running_installers(self):
        entries = module.registry(ROOT)
        self.assertIn('fish', entries)
        self.assertEqual(entries['fish'][1], ['editor', 'fish'])
        self.assertIn('tty', entries)
        self.assertTrue(entries['matrix'][2])

    def test_optional_hardware_is_skipped_by_default_but_can_be_requested(self):
        for argv, included in [(['check_setup.py'], False), (['check_setup.py', 'matrix'], True)]:
            with self.subTest(argv=argv), patch('sys.argv', argv), \
                    patch.object(module.Audit, 'item') as item, patch.object(module.Audit, 'packages'):
                module.main()
                selected = [call.args[0] for call in item.call_args_list]
                self.assertEqual('matrix' in selected, included)

    def test_package_queries_are_read_only(self):
        with patch.object(module.shutil, 'which', return_value='/usr/bin/pacman'), \
                patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess(
                    [], 1, '', "error: package 'missing-package' was not found")) as run:
            self.audit.packages(['missing-package'])
        run.assert_called_once_with(['pacman', '-Q', 'missing-package'], capture_output=True,
                                    text=True, env=dict(os.environ, LC_ALL='C'))
        self.assertEqual(self.audit.counts, {'DRIFT': 1})

    def test_package_database_failure_is_unknown(self):
        with patch.object(module.shutil, 'which', return_value='/usr/bin/pacman'), \
                patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess(
                    [], 1, '', 'error: could not open database')):
            self.audit.packages(['fish'])
        self.assertEqual(self.audit.counts, {'UNKNOWN': 1})

    def test_versioned_dependency_uses_pacman_dependency_query(self):
        with patch.object(module.shutil, 'which', return_value='/usr/bin/pacman'), \
                patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            self.audit.packages(['quickshell>=0.3.2'])
        self.assertEqual(run.call_args.args[0], ['pacman', '-T', 'quickshell>=0.3.2'])
        self.assertEqual(self.audit.counts, {'OK': 1})

    def test_system_copy_does_not_accept_symlink_or_wrong_group(self):
        self.target.symlink_to(self.source)
        self.audit.file(self.source, self.target)
        self.target.unlink()
        self.target.write_bytes(self.source.read_bytes())
        self.audit.file(self.source, self.target, gid=os.getgid() + 1)
        self.assertEqual(self.audit.counts, {'DRIFT': 2})

    def test_gsettings_query_failure_is_unknown(self):
        with patch.object(module.shutil, 'which', return_value='/usr/bin/gsettings'), \
                patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', '')):
            self.audit.value('setting', ['gsettings', 'get', 'schema', 'key'], 'true')
        self.assertEqual(self.audit.counts, {'UNKNOWN': 1})

    def test_cli_list_and_invalid_item(self):
        result = subprocess.run(['bash', str(ROOT / 'check-setup.sh'), '--list'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('pam upall', result.stdout)
        result = subprocess.run(['bash', str(ROOT / 'check-setup.sh'), 'invalid'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)

    def test_exit_codes_distinguish_drift_and_incomplete(self):
        def item(audit, name, entries):
            audit.report(self.state, name)

        for state, expected in [('OK', 0), ('DRIFT', 1), ('UNKNOWN', 2)]:
            with self.subTest(state=state), patch.object(module.Audit, 'item', item), \
                    patch.object(module.Audit, 'packages'), \
                    patch('sys.argv', ['check_setup.py', 'tty']):
                self.state = state
                self.assertEqual(module.main(), expected)
