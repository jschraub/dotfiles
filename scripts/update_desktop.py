#!/usr/bin/env python3
"""Plan and apply routine desktop updates without running bootstrap handlers."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile

from check_setup import Audit, registry
from install_access import FILES, greeter_config

ROOT = Path(__file__).resolve().parents[1]
MACHINES = ('mini-mecha', 'oki-mecha')
# Anchors identify existing installations, not merely installed application packages.
ANCHORS = {
    'hyprland': ('hyprland-{machine}/.config/hypr/hyprland.lua',),
    'quickshell': ('quickshell/.config/quickshell/atelier/shell.qml',),
    'ghostty': ('ghostty/.config/ghostty/config',),
    'fish': ('fish/.config/fish/config.fish',),
    'backgrounds': ('backgrounds/.config/backgrounds',),
    'avatars': ('avatars/.config/avatars',),
    'zed': ('zed/.config/zed/themes/atelier-amber.json',),
    'opencode': ('opencode/.config/opencode',),
    'theme': ('desktop-theme/.themes/Atelier/gtk-3.0/gtk.css', 'gtk-4.0/.config/gtk-4.0/gtk.css'),
}
SCRIPTS = {
    'hyprland': ('scripts/install_cursor.py',),
    'theme': ('theme/', 'scripts/apply_theme.py', 'scripts/render_theme.py', 'scripts/install_cursor.py', 'setup-theme.sh'),
    'zed': ('scripts/setup_zed.py', 'setup-zed.sh', 'scripts/apply_theme.py'),
}
MANUAL = ('setup-nautilus.sh', 'setup-tty.sh', 'setup-cloudflare-skills.sh',
          'setup-mattpocock-skills.sh', 'install-', 'pam-setup/', 'upall-setup/',
          'matrix-setup/', 'scripts/setup-atelier-access.sh', 'scripts/cleanup-atelier.sh')


class UpdateError(RuntimeError):
    pass


class Updater:
    def __init__(self, root=ROOT, home=None, system=Path('/'), hostname=None):
        self.root = root.resolve()
        self.home = Path.home() if home is None else home
        self.system = system
        self.hostname = socket.gethostname() if hostname is None else hostname
        self.non_interactive = False

    def run(self, argv, *, capture=False, allowed=(0,)):
        environment = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
        if self.non_interactive:
            environment['GIT_TERMINAL_PROMPT'] = '0'
            environment['GIT_SSH_COMMAND'] = environment.get('GIT_SSH_COMMAND', shlex.quote(environment.get('GIT_SSH', 'ssh'))) + ' -oBatchMode=yes'
        result = subprocess.run([str(arg) for arg in argv], cwd=self.root, text=True,
                                capture_output=capture, env=environment,
                                stdin=subprocess.DEVNULL if self.non_interactive else None)
        if result.returncode not in allowed:
            raise UpdateError(f'Command failed ({result.returncode}): {shlex.join(map(str, argv))}'
                              + (f'\n{result.stderr.strip()}' if capture else ''))
        return result

    def git(self, *args):
        return self.run(['git', *args], capture=True).stdout.strip()

    def preflight(self, requested=None):
        if self.git('rev-parse', '--show-toplevel') != str(self.root):
            raise UpdateError('Run from the primary dotfiles checkout, not a nested repository.')
        if self.git('status', '--porcelain', '--untracked-files=no'):
            raise UpdateError('Tracked files have local changes. Commit or preserve them yourself; nothing was stashed/reset.')
        for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply'):
            path = Path(self.git('rev-parse', '--git-path', name))
            if (self.root / path).exists():
                raise UpdateError('Finish the in-progress Git operation before updating.')
        branch = self.git('symbolic-ref', '--quiet', '--short', 'HEAD')
        if branch != 'main' or self.git('rev-parse', '--abbrev-ref', '@{upstream}') != 'origin/main':
            raise UpdateError('Routine updates require main tracking origin/main; no branches are switched automatically.')
        config = Path(os.environ.get('XDG_CONFIG_HOME') or self.home / '.config')
        if config != self.home / '.config':
            raise UpdateError('Custom XDG_CONFIG_HOME needs explicit setup; routine Stow updates target ~/.config.')
        installed = []
        target = config / 'hypr/hyprland.lua'
        for machine in MACHINES:
            source = self.root / f'hyprland-{machine}/.config/hypr/hyprland.lua'
            if target.resolve() == source.resolve():
                installed.append(machine)
        host = next((name for name in MACHINES if name == self.hostname), None)
        choices = {name for name in [requested, host, *installed] if name}
        if len(choices) != 1 or not choices.issubset(MACHINES):
            raise UpdateError('Machine profile is unknown or disagrees with hostname/installed links. Resolve it before updating.')
        machine = choices.pop()
        if installed != [machine]:
            raise UpdateError('The machine profile is not linked to this checkout. Use setup.sh for initial installation.')
        entries = registry(self.root)
        items = []
        for item, anchors in ANCHORS.items():
            for anchor in anchors:
                relative = Path(anchor.format(machine=machine))
                source = self.root / relative
                target = self.home / Path(*relative.parts[1:])
                # An application directory may be a real Stow merge directory.
                owned = target.resolve() == source.resolve()
                if source.is_dir() and target.is_dir() and not owned:
                    owned = any((target / file.relative_to(source)).resolve() == file.resolve()
                                for file in source.rglob('*') if file.is_file())
                if owned:
                    items.append(item)
                    break
        if not {'hyprland', 'quickshell', 'theme'}.issubset(items):
            raise UpdateError('An installed Atelier desktop/theme is required. Use setup.sh for initial installation.')
        packages = self.stow_packages(items, entries, machine)
        # Include ignored files too: Stow does not use Git's ignore rules.
        untracked = self.git('ls-files', '--others', '-z').split('\0')
        unsafe = [name for name in untracked if name and name.split('/')[0] in packages]
        if unsafe:
            raise UpdateError('Untracked files inside managed Stow sources could be installed; move them aside first:\n' + '\n'.join(unsafe))
        return machine, items, entries

    @staticmethod
    def stow_packages(items, entries, machine):
        packages = []
        for item in items:
            packages.extend(entries[item][1])
            if item == 'hyprland':
                packages.extend(['editor', 'hyprland-common', f'hyprland-{machine}'])
        return list(dict.fromkeys(packages))

    def state_path(self, machine):
        base = Path(os.environ.get('XDG_STATE_HOME') or self.home / '.local/state')
        key = hashlib.sha256(str(self.root).encode()).hexdigest()[:16]
        return base / 'atelier/updates' / f'{machine}-{key}.json'

    def baseline(self, machine):
        path = self.state_path(machine)
        if not path.exists():
            return None
        try:
            state = json.loads(path.read_text())
            revision = state['revision']
            if (state['machine'] != machine or state['checkout'] != str(self.root)
                    or len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision)):
                raise ValueError()
            items = state.get('items', [])
            if not isinstance(items, list) or any(not isinstance(item, str) or item not in ANCHORS for item in items):
                raise ValueError()
            self.git('cat-file', '-e', revision + '^{commit}')
            if self.run(['git', 'merge-base', '--is-ancestor', revision, 'HEAD'], capture=True, allowed=(0, 1)).returncode:
                raise ValueError()
            return revision
        except (ValueError, KeyError, TypeError, UpdateError):
            raise UpdateError(f'Invalid/unrelated success record: {path}. Inspect it; it was not overwritten.') from None

    def access_files(self):
        ui = 'quickshell/.config/quickshell/atelier/'
        files = {ui + name: '/etc/atelier/access/' + name for name in FILES}
        files.update({
            'auth-setup/qmldir': '/etc/atelier/access/qmldir',
            'backgrounds/.config/backgrounds/tolkien/balrog.jpg': '/usr/share/atelier/access/background.jpg',
            'greetd-setup/greeter-avatar.png': f'/usr/share/atelier/access/avatars/{os.getuid()}.png',
            'auth-setup/pam/atelier-lock': '/etc/pam.d/atelier-lock',
            'auth-setup/pam/atelier-fingerprint': '/etc/pam.d/atelier-fingerprint',
            'greetd-setup/etc/greetd/hyprland.lua': '/etc/greetd/atelier-hyprland.lua',
        })
        return files

    def access_status(self, baseline=None):
        staged = (self.system / 'etc/atelier/access').is_dir()
        if not staged:
            return False, []
        differences = []
        for source, destination in self.access_files().items():
            expected = (self.root / source).read_bytes()
            if source == 'greetd-setup/etc/greetd/hyprland.lua':
                expected = greeter_config(expected.decode()).encode()
            target = self.system / destination.lstrip('/')
            if target.is_symlink() or not target.is_file() or target.read_bytes() != expected:
                if source.startswith('auth-setup/pam/') and target.is_file():
                    previous = self.run(['git', 'show', f'{baseline}:{source}'], capture=True).stdout.encode() if baseline else None
                    if target.is_symlink() or target.read_bytes() != previous:
                        raise UpdateError(f'Local/unknown PAM policy differs: {destination}. Review it manually; routine updates will not overwrite it.')
                differences.append(destination)
        return True, differences

    def missing_packages(self, items, entries):
        dependencies = ['stow']
        for item in items:
            dependencies.extend(entries[item][0])
        selector = self.home / '.config/dotfiles/lock-screen'
        if selector.is_file() and selector.read_text().strip() == 'atelier':
            dependencies = [name for name in dependencies if name != 'hyprlock']
        if (self.system / 'etc/atelier/access').is_dir():
            dependencies.extend(entries['access'][0])
        dependencies = list(dict.fromkeys(dependencies))
        result = self.run(['pacman', '-T', *dependencies], capture=True, allowed=(0, 127))
        missing = result.stdout.splitlines()
        if any(name not in dependencies for name in missing) or bool(missing) != (result.returncode == 127):
            raise UpdateError('Unexpected dependency query response; no packages were installed.')
        return missing

    def plan(self, machine, items, entries):
        revision = self.git('rev-parse', 'HEAD')
        baseline = self.baseline(machine)
        previous_items = json.loads(self.state_path(machine).read_text()).get('items', []) if baseline else []
        changes = self.git('diff', '--name-only', '-z', baseline, revision).split('\0') if baseline else []
        changes = [path for path in changes if path]
        selected = []
        for item in items:
            prefixes = tuple(package + '/' for package in self.stow_packages([item], entries, machine)) + SCRIPTS.get(item, ())
            if item not in previous_items or 'setup.sh' in changes or any(path.startswith(prefixes) for path in changes):
                selected.append(item)
        staged, access = self.access_status(baseline)
        missing = self.missing_packages(items, entries)
        manual = [path for path in changes if path.startswith(MANUAL) or path.endswith('/fish_plugins')]
        return dict(machine=machine, revision=revision, baseline=baseline, changes=changes,
                    items=items, selected=selected, stow=self.stow_packages(selected, entries, machine),
                    missing=missing, staged=staged, access=access, manual=manual)

    def show(self, plan):
        print(f"\nMachine: {plan['machine']}\nCheckout: {self.root}")
        ahead, behind = self.git('rev-list', '--left-right', '--count', 'HEAD...origin/main').split()
        print(f'Cached origin/main: {ahead} local-only, {behind} incoming commits')
        print('Baseline: ' + (plan['baseline'][:12] if plan['baseline'] else 'first update; reconcile installed configuration once'))
        if plan['baseline'] and plan['baseline'] != plan['revision']:
            print(self.git('log', '--oneline', plan['baseline'] + '..' + plan['revision']))
        print('Installed scope: ' + ' '.join(plan['items']))
        print('Refresh: ' + (' '.join(plan['selected']) or 'no source changes'))
        print('Restow: ' + (' '.join(plan['stow']) or 'none'))
        print('Required packages: ' + (' '.join(plan['missing']) or 'already satisfied'))
        print('Root-owned authentication bundle: ' + ('approval required' if plan['access'] else 'matches' if plan['staged'] else 'not migrated; activation wizard remains separate'))
        for path in plan['access']:
            print('  Refresh copy: ' + path)
        for path in plan['manual']:
            print('  Manual review (bootstrap/policy not executed): ' + path)
        print('No full system upgrade, package cleanup, Fisher update, authentication activation, logout or reboot.')

    def validate(self):
        self.run([sys.executable, '-B', 'scripts/render_theme.py', '--check'])
        self.run(['Hyprland', '--verify-config', '-c', self.home / '.config/hypr/hyprland.lua'])

    def simulate_stow(self, packages):
        if packages:
            if not shutil.which('stow'):
                print('Stow simulation deferred until its missing dependency is installed.')
                return
            self.run(['stow', '--simulate', '--restow', '--no-folding', '--dir', self.root,
                      '--target', self.home, *packages], capture=True)

    def audit(self, plan):
        class UpdateAudit(Audit):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.blocking_unknown = []

            def report(self, state, label, detail=''):
                super().report(state, label, detail)
                if state == 'UNKNOWN' and label not in ('runtime appearance', 'authentication runtime', 'Fish plugins'):
                    self.blocking_unknown.append(label)

        audit = UpdateAudit(root=self.root, home=self.home, machine=plan['machine'])
        entries = registry(self.root)
        audit.packages(['stow'])
        for item in plan['items'] + (['access'] if plan['staged'] else []):
            audit.item(item, entries)
        print('\nAudit: ' + ', '.join(f'{audit.counts[state]} {state}' for state in ('OK', 'DRIFT', 'UNKNOWN')))
        if audit.counts['DRIFT'] or audit.blocking_unknown:
            raise UpdateError('Audit needs attention. No success revision was recorded; rerun after resolving it.')

    def apply(self, plan):
        if self.non_interactive and (plan['missing'] or plan['access']):
            raise UpdateError('Non-interactive update needs new dependencies or a privileged authentication refresh. '
                              'Run ./update.sh interactively to review/approve it. No success revision recorded.')
        if self.git('rev-parse', 'HEAD') != plan['revision'] or self.git('status', '--porcelain', '--untracked-files=no'):
            raise UpdateError('Checkout changed after planning. Rerun; no configuration was applied.')
        self.simulate_stow(plan['stow'])
        if plan['missing']:
            helper = next((name for name in ('paru', 'yay') if shutil.which(name)), None)
            self.run(([helper] if helper else ['sudo', 'pacman']) + ['-S', '--needed', *plan['missing']])
            remaining = self.missing_packages(plan['items'], registry(self.root))
            if remaining:
                raise UpdateError('Required dependencies are still unsatisfied: ' + ' '.join(remaining))
        self.simulate_stow(plan['stow'])
        if plan['stow']:
            self.run(['stow', '--restow', '--no-folding', '--dir', self.root, '--target', self.home, *plan['stow']])
        if 'theme' in plan['selected']:
            self.run([sys.executable, '-B', 'scripts/apply_theme.py'])
        elif 'hyprland' in plan['selected']:
            self.run([sys.executable, '-B', 'scripts/install_cursor.py'])
        if 'zed' in plan['selected']:
            self.run([sys.executable, '-B', 'scripts/setup_zed.py', '--no-runtime'])
        if plan['access']:
            if not confirm('Refresh the listed root-owned UI/PAM/assets with sudo? Existing differing copies are backed up. Selection is unchanged.'):
                raise UpdateError('Authentication refresh deferred. No success revision recorded; rerun when ready.')
            self.run(['sudo', sys.executable, '-B', self.root / 'scripts/install_access.py', '--account', pwd.getpwuid(os.getuid()).pw_name])
        self.validate()
        if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE') and any(item in plan['selected'] for item in ('hyprland', 'quickshell')):
            self.run(['hyprctl', 'reload'])
            errors = self.run(['hyprctl', 'configerrors'], capture=True).stdout.strip()
            if errors:
                raise UpdateError('Hyprland reports configuration errors; no success revision recorded.\n' + errors)
        if os.environ.get('WAYLAND_DISPLAY'):
            # Health-only IPC: never kill/restart the shell or an authentication process.
            if self.run(['qs', 'ipc', '-c', 'atelier', 'call', 'shell', 'health'], capture=True).stdout.strip() != 'ready':
                raise UpdateError('Atelier is not ready. Inspect qs log -c atelier; no success revision recorded.')
        self.audit(plan)
        if self.git('rev-parse', 'HEAD') != plan['revision'] or self.git('status', '--porcelain', '--untracked-files=no'):
            raise UpdateError('Checkout changed during the update; no success revision recorded.')
        path = self.state_path(plan['machine'])
        data = dict(version=1, machine=plan['machine'], checkout=str(self.root),
                    revision=plan['revision'], items=plan['items'])
        descriptor, temporary = tempfile.mkstemp(prefix='.update-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w') as output:
                json.dump(data, output, indent=2)
                output.write('\n')
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        print(f"\nUpdated successfully to {plan['revision'][:12]}. Record: {path}")
        print('Open a new Fish shell; reopen GTK/editor/browser apps if their configuration changed.')
        if plan['access']:
            print('Manually test password/fingerprint unlock, all displays, resume and a fresh login. No session was restarted.')
        for path in plan['manual']:
            print('Manual follow-up: ' + path)


def confirm(message):
    return input(message + ' [y/N] ').strip().lower() in ('y', 'yes')


@contextmanager
def update_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise UpdateError('Another updater is running for this checkout/machine.') from None
        yield


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='read-only local validation/audit; no fetch or state writes')
    mode.add_argument('--dry-run', action='store_true', help='read-only plan against the current checkout; no fetch or state writes')
    parser.add_argument('--non-interactive', action='store_true',
                        help='skip routine confirmations; never prompt; stop if dependencies/authentication need approval')
    parser.add_argument('--machine', choices=MACHINES, default=os.environ.get('HYPR_MACHINE'))
    args = parser.parse_args(argv)
    if os.geteuid() == 0:
        raise UpdateError('Run as your normal desktop user, not with sudo.')
    updater = Updater()
    updater.non_interactive = args.non_interactive
    machine, items, entries = updater.preflight(args.machine)
    if args.check or args.dry_run:
        print('READ ONLY: current checkout and cached origin/main only; remote changes are not fetched.')
        plan = updater.plan(machine, items, entries)
        updater.show(plan)
        updater.validate()
        updater.simulate_stow(plan['stow'])
        if args.check:
            updater.audit(plan)
        return 0
    with update_lock(updater.state_path(machine)):
        updater.validate()
        if not args.non_interactive and not confirm('Fetch origin/main and fast-forward this checkout? Linked applications may automatically reload changed files.'):
            raise UpdateError('Cancelled; checkout unchanged.')
        before = updater.git('rev-parse', 'HEAD')
        updater.run(['git', 'fetch', 'origin'])
        updater.preflight(args.machine)
        # Reject ahead/diverged local branches, even though merge --ff-only would
        # otherwise accept an ahead branch as "already up to date".
        if updater.run(['git', 'merge-base', '--is-ancestor', 'HEAD', 'origin/main'], capture=True, allowed=(0, 1)).returncode:
            raise UpdateError('Local main is ahead of or diverged from origin/main. Resolve it manually; nothing was reset.')
        updater.run(['git', 'merge', '--ff-only', 'origin/main'])
        after = updater.git('rev-parse', 'HEAD')
        changed = updater.git('diff', '--name-only', before, after).splitlines()
        if any(path in changed for path in ('update.sh', 'scripts/update_desktop.py', 'scripts/check_setup.py', 'scripts/install_access.py')):
            raise UpdateError('Updater code changed. Rerun ./update.sh to use the new implementation before applying configuration.')
        machine, items, entries = updater.preflight(args.machine)
        plan = updater.plan(machine, items, entries)
        updater.show(plan)
        updater.validate()
        updater.simulate_stow(plan['stow'])
        if not args.non_interactive and not confirm('Apply this plan and audit the installed desktop?'):
            raise UpdateError('Apply cancelled. Checkout is pulled; no success revision recorded.')
        updater.apply(plan)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (UpdateError, OSError, ValueError, EOFError, KeyboardInterrupt) as error:
        print(f'Update stopped: {error}', file=sys.stderr)
        raise SystemExit(1)
