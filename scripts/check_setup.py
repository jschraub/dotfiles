"""Read-only comparison of installed configuration with this working checkout."""
import argparse
import importlib.util
import json
from collections import Counter
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import stat
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def registry(root):
    # setup.sh is safe to source; never call main, handlers, or installers.
    result = subprocess.run([
        'bash', '-c', 'source "$1"; for id in "${ORDER[@]}"; do '
        'printf "%s\\0%s\\0%s\\0%s\\0" "$id" "${PKGS[$id]:-}" "${STOW[$id]:-}" "${OPTIONAL[$id]:-0}"; done',
        'audit', str(root / 'setup.sh'),
    ], check=True, capture_output=True, text=True)
    fields = result.stdout.split('\0')[:-1]
    return {fields[i]: (fields[i + 1].split(), fields[i + 2].split(), fields[i + 3] == '1')
            for i in range(0, len(fields), 4)}


class Audit:
    def __init__(self, root=ROOT, home=None, machine=None, verbose=False):
        self.root = root
        self.home = Path.home() if home is None else home
        self.machine = machine
        self.verbose = verbose
        self.counts = Counter()

    def report(self, state, label, detail=''):
        self.counts[state] += 1
        if state != 'OK' or self.verbose:
            print(f'[{state}] {label}' + (f': {detail}' if detail else ''))

    def file(self, source, target, linked=False, mode=None, uid=None, gid=None):
        try:
            if not linked and target.is_symlink():
                self.report('DRIFT', str(target), 'installer expects a regular copy, not a symlink')
                return
            metadata = target.stat()
            if not stat.S_ISREG(metadata.st_mode):
                self.report('DRIFT', str(target), 'not a regular file')
            elif source.read_bytes() != target.read_bytes():
                self.report('DRIFT', str(target), f'content differs from {source.relative_to(self.root)}')
            elif linked and source.resolve() != target.resolve():
                self.report('DRIFT', str(target), 'content matches, but not linked to this checkout')
            else:
                if mode is not None and metadata.st_mode & 0o7777 != mode:
                    self.report('DRIFT', str(target), f'expected permissions {mode:o}')
                elif uid is not None and metadata.st_uid != uid:
                    self.report('DRIFT', str(target), f'expected owner UID {uid}')
                elif gid is not None and metadata.st_gid != gid:
                    self.report('DRIFT', str(target), f'expected group GID {gid}')
                else:
                    self.report('OK', str(target))
        except FileNotFoundError as exc:
            if exc.filename == str(target):
                self.report('DRIFT', str(target), 'broken link' if target.is_symlink() else 'missing')
            else:
                self.report('UNKNOWN', str(target), 'source file unavailable')
        except (OSError, ValueError) as exc:
            self.report('UNKNOWN', str(target), f'cannot compare ({type(exc).__name__})')

    def stow(self, package):
        source = self.root / package
        if not source.is_dir():
            self.report('UNKNOWN', package, 'source package missing')
            return
        for file in sorted(source.rglob('*')):
            if file.is_file():
                self.file(file, self.home / file.relative_to(source), linked=True)

    def packages(self, packages):
        if packages and not shutil.which('pacman'):
            self.report('UNKNOWN', 'packages', 'pacman unavailable')
            return
        for package in packages:
            if package == 'waybar>=0.16.0':
                git = subprocess.run(['pacman', '-Q', 'waybar-git'], capture_output=True)
                if git.returncode == 0:
                    self.report('OK', 'Waybar Git fallback', 'rolling build; stable replacement uses setup-waybar.sh')
                    continue
                result = subprocess.run(['pacman', '-T', package], capture_output=True, text=True)
                if result.returncode == 0:
                    self.report('OK', f'package {package}')
                elif result.returncode == 127 and package in result.stdout.splitlines():
                    self.report('DRIFT', 'Waybar Lua support', 'requires stable >=0.16.0 or waybar-git; run ./setup-waybar.sh')
                else:
                    self.report('UNKNOWN', 'Waybar Lua support', 'dependency query failed')
                continue
            if re.search(r'[<>=]', package):
                result = subprocess.run(['pacman', '-T', package], capture_output=True, text=True)
                if result.returncode == 0:
                    self.report('OK', f'package {package}')
                elif result.returncode == 127 and package in result.stdout.splitlines():
                    self.report('DRIFT', f'package {package}', 'missing or version too old')
                else:
                    self.report('UNKNOWN', f'package {package}', 'dependency query failed')
                continue
            result = subprocess.run(['pacman', '-Q', package], capture_output=True, text=True,
                                    env=dict(os.environ, LC_ALL='C'))
            if result.returncode == 0:
                self.report('OK', f'package {package}')
            elif result.returncode == 1 and f"package '{package}' was not found" in result.stderr:
                self.report('DRIFT', f'package {package}', 'not installed')
            else:
                self.report('UNKNOWN', f'package {package}', 'package query failed')

    def value(self, label, command, expected):
        if not shutil.which(command[0]):
            self.report('UNKNOWN', label, f'{command[0]} unavailable')
            return
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            self.report('UNKNOWN', label, 'query failed; no settings were changed')
        else:
            self.report('OK' if result.stdout.strip() == expected else 'DRIFT', label,
                        '' if result.stdout.strip() == expected else 'value differs from installer')

    def directory(self, target, mode, uid, gid):
        try:
            metadata = target.lstat()
            matches = (stat.S_ISDIR(metadata.st_mode) and metadata.st_mode & 0o7777 == mode
                       and metadata.st_uid == uid and metadata.st_gid == gid)
            self.report('OK' if matches else 'DRIFT', str(target),
                        '' if matches else f'expected directory owner {uid}:{gid}, permissions {mode:o}')
        except FileNotFoundError:
            self.report('DRIFT', str(target), 'missing directory')
        except OSError:
            self.report('UNKNOWN', str(target), 'cannot inspect directory')

    def tty(self):
        self.packages(['terminus-font', 'fish'])
        self.file(self.root / 'fish/.config/fish/tty.fish', self.home / '.config/fish/tty.fish', linked=True)
        self.file(self.root / 'fish/.config/fish/conf.d/00-atelier-palette.fish',
                  self.home / '.config/fish/conf.d/00-atelier-palette.fish', linked=True)
        try:
            text = Path('/etc/vconsole.conf').read_text()
            fonts = re.findall(r'^\s*FONT\s*=\s*["\']?([^\s"\']+)', text, re.MULTILINE)
            self.report('OK' if fonts == ['ter-v16n'] else 'DRIFT', 'console font', 'expected ter-v16n')
        except OSError as exc:
            self.report('DRIFT' if isinstance(exc, FileNotFoundError) else 'UNKNOWN',
                        '/etc/vconsole.conf', 'cannot read console font')
        try:
            text = (self.home / '.config/fish/config.fish').read_text()
            active = any(line.strip() in ['source ~/.config/fish/tty.fish',
                                         'test -f ~/.config/fish/tty.fish; and source ~/.config/fish/tty.fish']
                         for line in text.splitlines())
            self.report('OK' if active else 'DRIFT', 'TTY Fish config hook')
        except FileNotFoundError:
            self.report('DRIFT', 'TTY Fish config hook', 'config.fish missing')
        except OSError:
            self.report('UNKNOWN', 'TTY Fish config hook', 'cannot read config.fish')

    def greetd(self):
        self.packages(['greetd', 'greetd-regreet', 'hyprland', 'dbus', 'ttf-cascadia-code-nerd'])
        try:
            greeter = pwd.getpwnam('greeter')
        except KeyError:
            self.report('DRIFT', 'greeter user', 'missing')
            greeter = None
        self.directory(Path('/etc/greetd'), 0o755, 0, 0)
        if greeter:
            for path in ['/var/lib/regreet', '/var/log/regreet']:
                self.directory(Path(path), 0o750, greeter.pw_uid, greeter.pw_gid)
        for name in ['config.toml', 'hyprland.lua', 'regreet.toml', 'regreet.css']:
            self.file(self.root / 'greetd-setup/etc/greetd' / name, Path('/etc/greetd') / name,
                      mode=0o640 if name == 'config.toml' else 0o644,
                      uid=0, gid=0)
        self.file(self.root / 'greetd-setup/etc/pam.d/greetd-greeter', Path('/etc/pam.d/greetd-greeter'))
        self.file(self.root / 'backgrounds/.config/backgrounds/tolkien/balrog.jpg',
                  Path('/usr/share/backgrounds/greeter-tolkien.jpg'))
        self.file(self.root / 'greetd-setup/greeter-avatar.png', Path('/usr/share/backgrounds/greeter-avatar.png'))
        if shutil.which('systemctl'):
            result = subprocess.run(['systemctl', 'is-enabled', 'greetd'], capture_output=True, text=True)
            state = result.stdout.strip()
            if state in ['enabled', 'disabled', 'masked', 'not-found']:
                self.report('OK' if state == 'enabled' else 'DRIFT', 'greetd service', state)
            else:
                self.report('UNKNOWN', 'greetd service', 'cannot determine persistent enablement')
        else:
            self.report('UNKNOWN', 'greetd service', 'systemctl unavailable')

    def upall(self):
        self.file(self.root / 'upall-setup/usr/local/libexec/upall-pacman',
                  Path('/usr/local/libexec/upall-pacman'), mode=0o755, uid=0, gid=0)
        target = Path('/etc/sudoers.d/upall-pacman')
        expected = f'{pwd.getpwuid(os.getuid()).pw_name} ALL=(root) NOPASSWD: /usr/local/libexec/upall-pacman\n'
        try:
            same = not target.is_symlink() and target.read_text() == expected
            metadata = target.stat()
            same = same and metadata.st_uid == 0 and metadata.st_gid == 0 and metadata.st_mode & 0o7777 == 0o440
            self.report('OK' if same else 'DRIFT', str(target), '' if same else 'policy/owner/permissions differ')
        except FileNotFoundError:
            self.report('DRIFT', str(target), 'missing')
        except OSError:
            self.report('UNKNOWN', str(target), 'not readable; inspect as administrator (audit never runs sudo)')

    def nautilus(self):
        self.packages(['nautilus', 'polkit-gnome', 'gvfs', 'gvfs-mtp', 'gvfs-smb', 'python', 'inter-font', 'breeze-icons'])
        self.stow('gtk-4.0')
        self.stow('desktop-theme')
        for schema, key, expected in [
            ('org.gnome.desktop.interface', 'color-scheme', "'prefer-dark'"),
            ('org.gnome.desktop.interface', 'gtk-theme', "'Atelier'"),
            ('org.gnome.nautilus.preferences', 'default-folder-viewer', "'list-view'"),
            ('org.gnome.nautilus.list-view', 'default-zoom-level', "'small'"),
            ('org.gnome.desktop.wm.preferences', 'button-layout', "''"),
            ('org.gnome.nautilus.preferences', 'show-hidden-files', 'true'),
            ('org.gnome.nautilus.preferences', 'default-sort-order', "'name'"),
            ('org.gnome.nautilus.preferences', 'recursive-search', "'local-only'"),
        ]:
            self.value(f'{schema} {key}', ['gsettings', 'get', schema, key], expected)

    def theme(self):
        result = subprocess.run(['python3', str(self.root / 'scripts/render_theme.py'), '--check'],
                                capture_output=True, text=True)
        self.report('OK' if result.returncode == 0 else 'DRIFT', 'generated theme palettes',
                    '' if result.returncode == 0 else 'run python3 scripts/render_theme.py')
        for key, expected in [('gtk-theme', "'Atelier'"), ('color-scheme', "'prefer-dark'"),
                              ('font-name', "'Inter 10'")]:
            self.value(f'org.gnome.desktop.interface {key}',
                       ['gsettings', 'get', 'org.gnome.desktop.interface', key], expected)
        if shutil.which('gsettings'):
            keys = subprocess.run(['gsettings', 'list-keys', 'org.gnome.desktop.interface'],
                                  capture_output=True, text=True).stdout.splitlines()
            if 'accent-color' in keys:
                self.value('GTK accent', ['gsettings', 'get', 'org.gnome.desktop.interface', 'accent-color'], "'yellow'")
        # Read JSONC without printing local settings; preserve all unrelated values.
        spec = importlib.util.spec_from_file_location('apply_theme', self.root / 'scripts/apply_theme.py')
        theme = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(theme)
        for path, key, expected in [
            (self.home / '.config/opencode/cli.json', 'theme', {'name': 'system', 'mode': 'dark'}),
            (self.home / '.config/Code/User/settings.json', 'workbench.colorTheme', 'Atelier Amber'),
            (self.home / '.config/zed/settings.json', 'theme', theme.ZED_THEME),
        ]:
            if not path.parent.exists():
                continue
            try:
                data = theme.parse_jsonc(path.read_text())
                self.report('OK' if data.get(key) == expected else 'DRIFT', f'{path}: {key}')
            except (OSError, ValueError):
                self.report('DRIFT', str(path), 'missing or invalid settings')
        for profile in theme.browser_profiles(self.home, self.home / '.config'):
            self.file(self.root / 'desktop-theme/.local/share/atelier/browser.css',
                      profile / 'chrome/atelier.css', linked=True)
            for relative, pattern in [
                ('chrome/userChrome.css', r'@import url\("atelier\.css"\);'),
                ('user.js', r'(?m)^[ \t]*user_pref\("toolkit\.legacyUserProfileCustomizations\.stylesheets",[ \t]*true\);'),
            ]:
                path = profile / relative
                try:
                    self.report('OK' if re.search(pattern, path.read_text()) else 'DRIFT', f'{path}: Atelier hook')
                except OSError:
                    self.report('DRIFT', str(path), 'missing or unreadable appearance hook')
        for package, relative in [
            ('ghostty', '.config/ghostty/themes/Atelier Amber'),
            ('ghostty', '.config/ghostty/atelier.css'),
            ('zed', '.config/zed/themes/atelier-amber.json'),
            ('fish', '.config/fish/conf.d/00-atelier-palette.fish'),
            ('claude', '.claude/atelier-palette.sh'),
        ]:
            rel = Path(relative)
            app_directory = self.home / rel.parts[0]
            if rel.parts[0] == '.config':
                app_directory /= rel.parts[1]
            if app_directory.exists():
                self.file(self.root / package / relative, self.home / relative, linked=True)
        self.report('UNKNOWN', 'runtime appearance', 'GTK/browser/editor reload and other-machine visuals require a visual check')

    def zed(self):
        spec = importlib.util.spec_from_file_location('apply_theme_for_zed_audit', self.root / 'scripts/apply_theme.py')
        theme = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(theme)
        path = self.home / '.config/zed/settings.json'
        try:
            data = theme.parse_jsonc(path.read_text())
            self.report('OK' if data.get('theme') == theme.ZED_THEME else 'DRIFT', f'{path}: theme')
        except (OSError, ValueError):
            self.report('DRIFT', str(path), 'missing or invalid Zed settings')
        self.value('default text editor', ['xdg-mime', 'query', 'default', 'text/plain'], 'atelier-editor.desktop')

    def external(self, item):
        # Installers follow moving upstream branches, not a committed version.
        locations = {
            'matrix': ('MATRIX_DIR', self.home / 'code/matrix', ['install.sh']),
            'cloudflare-skills': ('CLOUDFLARE_SKILLS_DIR', self.home / '.config/opencode/skills/cloudflare-skills', ['skills']),
            'mattpocock-skills': ('MATTPOCOCK_SKILLS_DIR', self.home / '.config/opencode/skills/mattpocock-skills',
                                 ['skills/productivity', 'skills/engineering']),
        }
        variable, default, paths = locations[item]
        checkout = Path(os.environ.get(variable) or default)
        for name in ['.git'] + paths:
            target = checkout / name
            try:
                metadata = target.stat()
                matches = (stat.S_ISREG(metadata.st_mode) and os.access(target, os.X_OK)
                           if name == 'install.sh' else stat.S_ISDIR(metadata.st_mode))
                self.report('OK' if matches else 'DRIFT', str(target), '' if matches else 'wrong type or permissions')
            except FileNotFoundError:
                self.report('DRIFT', str(target), 'missing')
            except OSError:
                self.report('UNKNOWN', str(target), 'cannot inspect checkout')
        self.report('UNKNOWN', item, 'upstream version and delegated installation are not pinned/audited; no network access')

    def item(self, item, entries):
        print(f'\n== {item} ==')
        packages, stow, _ = entries.get(item, ([], [], False))
        self.packages(packages)
        for package in stow:
            self.stow(package)
        if item == 'hyprland':
            self.stow('editor')
            self.stow('hyprland-common')
            if self.machine:
                self.stow(f'hyprland-{self.machine}')
            else:
                self.report('UNKNOWN', 'Hyprland profile', 'use --machine mini-mecha or --machine oki-mecha')
        elif item in ['tty', 'greetd', 'upall', 'nautilus', 'theme', 'zed']:
            getattr(self, item)()
        elif item == 'pam':
            self.file(self.root / 'pam-setup/etc/pam.d/hyprlock', Path('/etc/pam.d/hyprlock'), mode=0o644, uid=0, gid=0)
        elif item in ['matrix', 'cloudflare-skills', 'mattpocock-skills']:
            self.external(item)
        elif item == 'fish':
            for name in ['fisher', 'tide']:
                file = self.home / '.config/fish/functions' / f'{name}.fish'
                self.report('OK' if file.is_file() else 'DRIFT', f'Fish plugin {name}')
            self.report('UNKNOWN', 'Fish plugins', 'presence checked; upstream versions and runtime behavior not audited')


def main():
    entries = registry(ROOT)
    choices = list(entries) + ['pam', 'upall']
    parser = argparse.ArgumentParser(description='Read-only audit against the current checkout; no repairs, sudo, or network.')
    parser.add_argument('items', nargs='*', help='setup item names, pam, or upall; default: all')
    parser.add_argument('--list', action='store_true', help='list supported items')
    parser.add_argument('--verbose', action='store_true', help='also print matching checks')
    parser.add_argument('--machine', choices=['mini-mecha', 'oki-mecha'], default=os.environ.get('HYPR_MACHINE'))
    args = parser.parse_args()
    if args.list:
        print(' '.join(choices))
        return 0
    defaults = [item for item in choices if not entries.get(item, ([], [], False))[2]]
    items = args.items or defaults
    if items == ['all']:
        items = defaults
    if any(item not in choices for item in items):
        parser.error('unknown item; use --list')
    machine = args.machine
    if machine and machine not in ['mini-mecha', 'oki-mecha']:
        parser.error('invalid HYPR_MACHINE; use mini-mecha or oki-mecha')
    if not machine:
        machine = next((name for name in ['mini-mecha', 'oki-mecha'] if name in socket.gethostname()), None)
    audit = Audit(machine=machine, verbose=args.verbose)
    print(f'Baseline: current working checkout at {ROOT}')
    print('Only selected expectations are checked; no extra files are deleted or reported as drift.')
    if not args.items or args.items == ['all']:
        print('[SKIP] Matrix hardware and legacy waybar/wofi/wlogout are opt-in; audit explicitly when used.')
    audit.packages(['stow'])
    for item in dict.fromkeys(items):
        audit.item(item, entries)
    print('\nSummary: ' + ', '.join(f'{audit.counts[state]} {state}' for state in ['OK', 'DRIFT', 'UNKNOWN']))
    return 1 if audit.counts['DRIFT'] else 2 if audit.counts['UNKNOWN'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
