"""Updater integration tests: disposable Git repos/homes and recorded OS commands."""
from collections import Counter
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
sys.path.insert(0, str(ROOT / 'scripts'))
import update_desktop as update
sys.path.pop(0)


class RecordedUpdater(update.Updater):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = []
        self.missing = []
        self.fail_on = None
        self.audit_failure = False

    def run(self, argv, **kwargs):
        argv = list(map(str, argv))
        self.commands.append(argv)
        if argv[0] == 'git':
            return super().run(argv, **kwargs)
        if self.fail_on and self.fail_on in ' '.join(argv):
            raise update.UpdateError('injected failure')
        if argv[:2] == ['pacman', '-T']:
            return subprocess.CompletedProcess(argv, 127 if self.missing else 0, '\n'.join(self.missing), '')
        if '-S' in argv:
            self.missing = []
        return subprocess.CompletedProcess(argv, 0, 'ready\n' if argv[0] == 'qs' else '', '')

    def audit(self, plan):
        self.commands.append(['AUDIT'])
        if self.audit_failure:
            raise update.UpdateError('audit failed')


class DesktopUpdateTest(unittest.TestCase):
    def setUp(self):
        quiet = redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'repo'
        self.home = self.base / 'home'
        self.system = self.base / 'system'
        self.root.mkdir()
        self.home.mkdir()
        self.env = patch.dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'),
                              XDG_STATE_HOME=str(self.home / '.local/state'), HYPR_MACHINE='mini-mecha',
                              WAYLAND_DISPLAY='fixture', HYPRLAND_INSTANCE_SIGNATURE='fixture')
        self.env.start()
        self.addCleanup(self.env.stop)
        shutil.copyfile(ROOT / 'setup.sh', self.root / 'setup.sh')
        for item, anchors in update.ANCHORS.items():
            anchor = anchors[0].format(machine='mini-mecha')
            # Directory anchors include one representative tracked file.
            if item in ('backgrounds', 'avatars', 'opencode'):
                anchor += '/fixture.txt'
            source = self.root / anchor
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(item + '\n')
            target = self.home / Path(anchor).relative_to(Path(anchor).parts[0])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(os.path.relpath(source, target.parent))
        # Access sources exist even for an unmigrated machine.
        self.updater = RecordedUpdater(self.root, self.home, self.system, hostname='mini-mecha')
        for source in self.updater.access_files():
            path = self.root / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / source).read_bytes())
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.commit('initial')
        self.remote = self.base / 'remote.git'
        subprocess.run(['git', 'clone', '--bare', str(self.root), str(self.remote)], check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('fetch', 'origin')
        self.git('branch', '--set-upstream-to=origin/main')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-m', message)
        return self.git('rev-parse', 'HEAD')

    def plan(self):
        machine, items, entries = self.updater.preflight('mini-mecha')
        return self.updater.plan(machine, items, entries)

    def seed_state(self):
        path = self.updater.state_path('mini-mecha')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(machine='mini-mecha', checkout=str(self.root),
                                        revision=self.git('rev-parse', 'HEAD'), items=list(update.ANCHORS))))
        return path

    def remote_commit(self, relative, text):
        checkout = self.base / 'publisher'
        subprocess.run(['git', 'clone', str(self.remote), str(checkout)], check=True, capture_output=True)
        def git(*args):
            return subprocess.run(['git', *args], cwd=checkout, check=True, capture_output=True, text=True).stdout.strip()
        git('config', 'user.email', 'fixture@example.invalid')
        git('config', 'user.name', 'Fixture')
        path = checkout / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        git('add', '-A')
        git('commit', '-m', 'remote update')
        git('push', 'origin', 'main')
        return git('rev-parse', 'HEAD')

    def invoke(self, *args, answers=True):
        with patch.object(update, 'Updater', return_value=self.updater), patch.object(update.os, 'geteuid', return_value=1000), \
                patch.object(update, 'confirm', return_value=answers):
            return update.main(list(args))

    def stage_access(self):
        for source, destination in self.updater.access_files().items():
            contents = (self.root / source).read_bytes()
            if source == 'greetd-setup/etc/greetd/hyprland.lua':
                contents = update.greeter_config(contents.decode()).encode()
            target = self.system / destination.lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents)

    def test_first_run_reconciles_only_installed_items_without_bootstraps(self):
        plan = self.plan()
        self.assertIsNone(plan['baseline'])
        self.assertEqual(set(plan['items']), set(update.ANCHORS))
        self.assertNotIn('greetd', plan['items'])
        self.seed_state().unlink()
        self.updater.apply(plan)
        commands = '\n'.join(' '.join(command) for command in self.updater.commands)
        for forbidden in ('fisher', 'setup.sh', 'setup-nautilus.sh', '--activate-greeter', 'systemctl', 'kill', '-Syu'):
            self.assertNotIn(forbidden, commands)
        self.assertIn('stow --restow --no-folding', commands)
        zed = next(command for command in self.updater.commands if 'scripts/setup_zed.py' in command)
        self.assertIn('--no-runtime', zed, 'Routine updates must not rewrite editor associations')
        state = json.loads(self.updater.state_path('mini-mecha').read_text())
        self.assertEqual(state['revision'], plan['revision'])

    def test_selects_only_changed_installed_modules_and_tracks_manual_changes(self):
        self.seed_state()
        shell = self.root / 'quickshell/.config/quickshell/atelier/shell.qml'
        shell.write_text('changed\n')
        plugins = self.root / 'fish/.config/fish/fish_plugins'
        plugins.write_text('new-plugin\n')
        self.commit('desktop change')
        plan = self.plan()
        self.assertEqual(plan['selected'], ['quickshell', 'fish'])
        self.assertEqual(plan['manual'], ['fish/.config/fish/fish_plugins'])
        self.assertNotIn('hyprland-oki-mecha', plan['stow'])

    def test_other_machine_changes_do_not_apply_to_laptop(self):
        self.seed_state()
        path = self.root / 'hyprland-oki-mecha/.config/hypr/hyprland.lua'
        path.parent.mkdir(parents=True)
        path.write_text('desktop-specific\n')
        self.commit('other machine')
        self.assertEqual(self.plan()['selected'], [])

    def test_refuses_dirty_tracked_files_wrong_machine_and_untracked_stow_sources(self):
        source = self.root / 'ghostty/.config/ghostty/config'
        original = source.read_bytes()
        source.write_text('local settings\n')
        with self.assertRaisesRegex(update.UpdateError, 'local changes'):
            self.plan()
        self.assertEqual(source.read_text(), 'local settings\n')
        source.write_bytes(original)
        with self.assertRaisesRegex(update.UpdateError, 'disagrees'):
            self.updater.preflight('oki-mecha')
        backup = source.with_name('config.backup')
        backup.write_text('keep me')
        with self.assertRaisesRegex(update.UpdateError, 'Untracked files'):
            self.plan()
        self.assertEqual(backup.read_text(), 'keep me')

    def test_check_and_dry_run_do_not_fetch_write_state_or_apply(self):
        for option in ('--check', '--dry-run'):
            self.updater.commands.clear()
            before = sorted(str(path.relative_to(self.base)) for path in self.base.rglob('*'))
            self.assertEqual(self.invoke(option), 0)
            after = sorted(str(path.relative_to(self.base)) for path in self.base.rglob('*'))
            self.assertEqual(before, after)
            for command in self.updater.commands:
                self.assertNotIn('fetch', command)
                self.assertNotIn('merge', command)
                self.assertNotIn('sudo', command)
                self.assertNotIn('--restow', command if '--simulate' not in command else [])
            self.assertFalse(self.updater.state_path('mini-mecha').exists())

    def test_authentication_refresh_requires_separate_consent_and_never_activates(self):
        self.stage_access()
        path = self.system / 'etc/atelier/access/Theme.qml'
        path.write_text('older theme')
        plan = self.plan()
        self.assertEqual(plan['access'], ['/etc/atelier/access/Theme.qml'])
        record = self.seed_state()
        before = record.read_bytes()
        with patch.object(update, 'confirm', return_value=False), self.assertRaisesRegex(update.UpdateError, 'deferred'):
            self.updater.apply(plan)
        self.assertEqual(record.read_bytes(), before)
        self.updater.commands.clear()
        with patch.object(update, 'confirm', return_value=True):
            self.updater.apply(plan)
        commands = [command for command in self.updater.commands if command[0] == 'sudo']
        self.assertEqual(len(commands), 1)
        self.assertIn('--account', commands[0])
        self.assertNotIn('--activate-greeter', commands[0])

    def test_failures_do_not_advance_last_success(self):
        path = self.seed_state()
        before = path.read_bytes()
        source = self.root / 'quickshell/.config/quickshell/atelier/shell.qml'
        source.write_text('update\n')
        self.commit('update')
        plan = self.plan()
        self.updater.fail_on = 'stow --restow'
        with self.assertRaisesRegex(update.UpdateError, 'injected'):
            self.updater.apply(plan)
        self.assertEqual(path.read_bytes(), before)
        self.updater.fail_on = None
        self.updater.audit_failure = True
        with self.assertRaisesRegex(update.UpdateError, 'audit failed'):
            self.updater.apply(plan)
        self.assertEqual(path.read_bytes(), before)

    def test_provider_dependencies_and_native_locker_do_not_reinstall_hyprlock(self):
        selector = self.home / '.config/dotfiles/lock-screen'
        selector.parent.mkdir(parents=True)
        selector.write_text('atelier\n')
        self.updater.missing = ['wl-clipboard']
        plan = self.plan()
        query = next(command for command in self.updater.commands if command[:2] == ['pacman', '-T'])
        self.assertNotIn('hyprlock', query)
        self.assertEqual(plan['missing'], ['wl-clipboard'])

    def test_invalid_success_record_is_not_silently_replaced(self):
        path = self.seed_state()
        path.write_text('{invalid json')
        with self.assertRaisesRegex(update.UpdateError, 'Invalid/unrelated'):
            self.plan()
        self.assertEqual(path.read_text(), '{invalid json')

    def test_normal_run_fetches_fast_forwards_and_records_success(self):
        self.seed_state()
        revision = self.remote_commit('quickshell/.config/quickshell/atelier/shell.qml', 'new remote UI\n')
        self.assertEqual(self.invoke(), 0)
        self.assertIn(['git', 'fetch', 'origin'], self.updater.commands)
        self.assertIn(['git', 'merge', '--ff-only', 'origin/main'], self.updater.commands)
        self.assertEqual(json.loads(self.updater.state_path('mini-mecha').read_text())['revision'], revision)

    def test_updated_updater_requires_fresh_process_before_any_installation(self):
        record = self.seed_state()
        original = record.read_bytes()
        self.remote_commit('scripts/update_desktop.py', '# new updater implementation\n')
        with self.assertRaisesRegex(update.UpdateError, 'Updater code changed'):
            self.invoke()
        self.assertEqual(record.read_bytes(), original)
        self.assertFalse(any(command[0] == 'stow' for command in self.updater.commands))

    def test_ahead_local_main_is_rejected_without_resetting(self):
        path = self.root / 'local.txt'
        path.write_text('local commit\n')
        revision = self.commit('unpublished local work')
        with self.assertRaisesRegex(update.UpdateError, 'ahead of or diverged'):
            self.invoke()
        self.assertEqual(self.git('rev-parse', 'HEAD'), revision)
        self.assertEqual(path.read_text(), 'local commit\n')

    def test_cancel_before_fetch_leaves_checkout_and_success_untouched(self):
        path = self.seed_state()
        before = path.read_bytes()
        with self.assertRaisesRegex(update.UpdateError, 'Cancelled'):
            self.invoke(answers=False)
        self.assertNotIn(['git', 'fetch', 'origin'], self.updater.commands)
        self.assertEqual(path.read_bytes(), before)

    def test_non_interactive_updates_without_any_confirmation(self):
        self.seed_state()
        with patch.object(update, 'confirm', side_effect=AssertionError('must not prompt')):
            with patch.object(update, 'Updater', return_value=self.updater), patch.object(update.os, 'geteuid', return_value=1000):
                self.assertEqual(update.main(['--non-interactive']), 0)
        self.assertIn(['git', 'fetch', 'origin'], self.updater.commands)
        self.assertFalse(any(command[0] == 'sudo' for command in self.updater.commands))

    def test_non_interactive_defers_privileged_work_without_prompt_or_success(self):
        for kind in ('dependencies', 'authentication'):
            with self.subTest(kind=kind):
                self.updater.non_interactive = True
                record = self.seed_state()
                before = record.read_bytes()
                plan = self.plan()
                plan['missing'] = ['wl-clipboard'] if kind == 'dependencies' else []
                plan['access'] = ['/etc/atelier/access/Theme.qml'] if kind == 'authentication' else []
                self.updater.commands.clear()
                with patch.object(update, 'confirm', side_effect=AssertionError('must not prompt')):
                    with self.assertRaisesRegex(update.UpdateError, 'Run ./update.sh interactively'):
                        self.updater.apply(plan)
                self.assertEqual(record.read_bytes(), before)
                self.assertEqual(self.updater.commands, [])

    def test_non_interactive_commands_disable_stdin_and_git_authentication_prompts(self):
        self.updater.non_interactive = True
        result = subprocess.CompletedProcess(['git'], 0, '', '')
        with patch.object(update.subprocess, 'run', return_value=result) as run:
            update.Updater.run(self.updater, ['git', 'fetch', 'origin'])
        options = run.call_args.kwargs
        self.assertEqual(options['stdin'], subprocess.DEVNULL)
        self.assertEqual(options['env']['GIT_TERMINAL_PROMPT'], '0')
        self.assertIn('-oBatchMode=yes', options['env']['GIT_SSH_COMMAND'])

    def test_update_lock_excludes_concurrent_runs(self):
        path = self.updater.state_path('mini-mecha')
        with update.update_lock(path):
            with self.assertRaisesRegex(update.UpdateError, 'Another updater'):
                with update.update_lock(path):
                    self.fail('lock should not be acquired')

    def test_local_pam_customizations_are_never_automatically_replaced(self):
        self.stage_access()
        target = self.system / 'etc/pam.d/atelier-lock'
        target.write_text('local authentication policy\n')
        with self.assertRaisesRegex(update.UpdateError, 'PAM policy differs'):
            self.plan()
        self.assertEqual(target.read_text(), 'local authentication policy\n')

    def test_stow_simulation_preserves_foreign_configuration(self):
        if not shutil.which('stow'):
            self.skipTest('GNU Stow unavailable')
        target = self.home / '.config/quickshell/atelier/Theme.qml'
        target.write_text('foreign configuration\n')
        real = update.Updater(self.root, self.home, self.system, hostname='mini-mecha')
        with self.assertRaises(update.UpdateError):
            real.simulate_stow(['quickshell'])
        self.assertEqual(target.read_text(), 'foreign configuration\n')
        self.assertFalse(target.is_symlink())

    def test_stow_handles_folded_directories_without_modifying_checkout(self):
        if not shutil.which('stow'):
            self.skipTest('GNU Stow unavailable')
        target = self.home / '.config/ghostty'
        (target / 'config').unlink()
        target.rmdir()
        target.symlink_to(os.path.relpath(self.root / 'ghostty/.config/ghostty', target.parent), target_is_directory=True)
        real = update.Updater(self.root, self.home, self.system, hostname='mini-mecha')
        real.simulate_stow(['ghostty'])
        real.run(['stow', '--restow', '--no-folding', '--dir', self.root, '--target', self.home, 'ghostty'])
        self.assertEqual(self.git('status', '--porcelain', '--untracked-files=no'), '')
        self.assertEqual((target / 'config').resolve(), self.root / 'ghostty/.config/ghostty/config')

    def test_source_change_during_confirmation_stops_before_applying(self):
        plan = self.plan()
        path = self.root / 'ghostty/.config/ghostty/config'
        path.write_text('concurrent edit\n')
        self.updater.commands.clear()
        with self.assertRaisesRegex(update.UpdateError, 'changed after planning'):
            self.updater.apply(plan)
        self.assertTrue(all(command[0] == 'git' for command in self.updater.commands))

    def test_only_expected_manual_unknowns_allow_success(self):
        class FixtureAudit:
            unknown = 'runtime appearance'

            def __init__(self, **kwargs):
                self.counts = Counter()

            def packages(self, packages):
                pass

            def item(self, item, entries):
                self.report('UNKNOWN', self.unknown)

            def report(self, state, label, detail=''):
                self.counts[state] += 1

        plan = self.plan()
        with patch.object(update, 'Audit', FixtureAudit):
            update.Updater.audit(self.updater, plan)
            FixtureAudit.unknown = 'unreadable system configuration'
            with self.assertRaisesRegex(update.UpdateError, 'Audit needs attention'):
                update.Updater.audit(self.updater, plan)
