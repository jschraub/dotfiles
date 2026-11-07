#!/usr/bin/env python3
"""Install Atelier user appearance safely. No sudo, logout, or app termination."""
import argparse
import configparser
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ZED_THEME = {'mode': 'dark', 'dark': 'Atelier Amber', 'light': 'Atelier Amber'}


def backup(path):
    target = path.with_name(path.name + '.pre-atelier.' + datetime.now().strftime('%Y%m%d%H%M%S%f'))
    if path.is_symlink():
        target.symlink_to(os.readlink(path))
    else:
        shutil.copy2(path, target)
    print(f'Backup: {target}')
    return target


def link(source, target):
    if target.is_symlink() and target.resolve() == source.resolve():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_dir() and not target.is_symlink():
            raise ValueError(f'Refusing to replace directory: {target}')
        backup(target)
        target.unlink()
    target.symlink_to(os.path.relpath(source, target.parent))
    print(f'Linked: {target}')


def jsonc_mask(text):
    """Mask comments, retaining offsets and strings, then remove trailing commas."""
    token = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/')
    return token.sub(lambda m: m[0] if m[0].startswith('"') else
                     ''.join('\n' if ch == '\n' else ' ' for ch in m[0]), text)


def parse_jsonc(text):
    # Skip strings while removing trailing commas: literal ",}" is valid data.
    clean = re.sub(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])',
                   lambda m: '' if m[0] == ',' else m[0], jsonc_mask(text))
    return json.loads(clean)


def set_jsonc_value(text, key, value):
    """Replace one top-level setting without deleting comments or other values."""
    masked = jsonc_mask(text)
    parsed = parse_jsonc(text)
    if not isinstance(parsed, dict):
        raise ValueError('Settings must be a JSON object')
    if parsed.get(key) == value:
        return text
    encoded = json.dumps(value)
    tokens = list(re.finditer(r'"(?:\\.|[^"\\])*"|[{}\[\]:,]|[^\s{}\[\]:,]+', masked))
    depth = 0
    for i, token in enumerate(tokens):
        if depth == 1 and token[0].startswith('"') and json.loads(token[0]) == key and tokens[i+1][0] == ':':
            start = tokens[i+2].start()
            nested = 0
            for j in range(i+2, len(tokens)):
                end = tokens[j]
                if nested == 0 and end[0] in (',', '}'):
                    return text[:start] + encoded + text[tokens[j-1].end():]
                if end[0] in ('{', '['):
                    nested += 1
                elif end[0] in ('}', ']'):
                    nested -= 1
        if token[0] in ('{', '['):
            depth += 1
        elif token[0] in ('}', ']'):
            depth -= 1
    start = masked.index('{') + 1
    return text[:start] + '\n  ' + json.dumps(key) + ': ' + encoded + (',' if parsed else '') + text[start:]


def setting(path, key, value):
    previous = path.read_text() if path.exists() else '{}\n'
    updated = set_jsonc_value(previous, key, value)
    if updated != previous:
        if path.exists():
            backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated)
        print(f'Set {key}: {path}')


def browser_profiles(home, config):
    for base in [config / 'zen', home / '.mozilla/firefox', config / 'mozilla/firefox']:
        ini = base / 'profiles.ini'
        if not ini.is_file():
            continue
        profiles = configparser.ConfigParser(interpolation=None)
        profiles.read(ini)
        for name in profiles.sections():
            if name.startswith('Profile') and profiles.has_option(name, 'Path'):
                path = Path(profiles[name]['Path'])
                if profiles[name].get('IsRelative', '1') == '1':
                    path = base / path
                if path.is_dir():
                    yield path


def browser_theme(profile, source):
    link(source, profile / 'chrome/atelier.css')
    path = profile / 'chrome/userChrome.css'
    previous = path.read_text() if path.exists() else ''
    directive = '@import url("atelier.css");'
    if directive not in previous:
        if path.exists():
            backup(path)
        path.write_text(directive + '\n' + previous)
    path = profile / 'user.js'
    previous = path.read_text() if path.exists() else ''
    pattern = r'^[ \t]*user_pref\("toolkit\.legacyUserProfileCustomizations\.stylesheets",[ \t]*(?:true|false)\);[ \t]*$'
    directive = 'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);'
    updated = re.sub(pattern, directive, previous, flags=re.MULTILINE)
    if not re.search(pattern, previous, flags=re.MULTILINE):
        updated = previous.rstrip() + '\n// Atelier: browser chrome only.\n' + directive + '\n'
    if updated != previous:
        if path.exists():
            backup(path)
        path.write_text(updated)
    print(f'Browser chrome installed (takes effect on next browser start): {profile}')


def configure_zed(home, root=ROOT, config=None):
    config = config or home / '.config'
    link(root / 'zed/.config/zed/themes/atelier-amber.json', config / 'zed/themes/atelier-amber.json')
    path = config / 'zed/settings.json'
    # Never replace a user's settings file with a Stow link: Zed edits it itself.
    # Existing keymaps, fonts, language configuration and agent settings survive.
    previous = path.read_text() if path.exists() else '{}\n'
    parsed = parse_jsonc(previous)
    updated = set_jsonc_value(previous, 'theme', ZED_THEME)
    for key, value in {'ui_font_family': 'Inter', 'buffer_font_family': 'CaskaydiaCove Nerd Font',
                       'buffer_font_size': 13, 'base_keymap': 'VSCode'}.items():
        if key not in parsed:
            updated = set_jsonc_value(updated, key, value)
    if updated != previous:
        if path.exists():
            backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated)
        print(f'Configured Zed: {path}')


def apply(home, root=ROOT, config=None):
    config = config or home / '.config'
    # Explicit package roots: theme source/templates are never linked into HOME.
    for package in ['desktop-theme', 'gtk-4.0']:
        for source in sorted((root / package).rglob('*')):
            if source.is_file():
                relative = source.relative_to(root / package)
                target = config / relative.relative_to('.config') if relative.parts[0] == '.config' else home / relative
                link(source, target)
    for package, relative in [
        ('ghostty', '.config/ghostty/themes/Atelier Amber'),
        ('ghostty', '.config/ghostty/atelier.css'),
        ('fish', '.config/fish/conf.d/00-atelier-palette.fish'),
        ('claude', '.claude/atelier-palette.sh'),
    ]:
        rel = Path(relative)
        target = config / rel.relative_to('.config') if rel.parts[0] == '.config' else home / rel
        app_directory = config / rel.parts[1] if rel.parts[0] == '.config' else home / rel.parts[0]
        if app_directory.exists():
            link(root / package / relative, target)
    # OpenCode V2's documented terminal-derived theme follows Ghostty's ANSI colors.
    # Preserve every other CLI preference and any comments.
    cli = config / 'opencode/cli.json'
    if cli.parent.exists():
        setting(cli, '$schema', 'https://opencode.ai/v2/cli.json')
        setting(cli, 'theme', {'name': 'system', 'mode': 'dark'})
    code = config / 'Code/User/settings.json'
    if code.parent.exists():
        setting(code, 'workbench.colorTheme', 'Atelier Amber')
    if (config / 'zed').exists():
        configure_zed(home, root, config)
    for profile in browser_profiles(home, config):
        browser_theme(profile, root / 'desktop-theme/.local/share/atelier/browser.css')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-runtime', action='store_true', help='install files only; do not change GSettings or reload apps')
    args = parser.parse_args()
    subprocess.run(['python3', str(ROOT / 'scripts/render_theme.py'), '--check'], check=True)
    home = Path.home()
    config = Path(os.environ.get('XDG_CONFIG_HOME') or home / '.config')
    subprocess.run(['python3', str(ROOT / 'scripts/install_cursor.py')], check=True)
    apply(home, config=config)
    if not args.no_runtime:
        if shutil.which('gsettings'):
            preferences = {'gtk-theme': 'Atelier', 'color-scheme': 'prefer-dark', 'accent-color': 'yellow', 'font-name': 'Inter 10',
                           'cursor-theme': 'Bibata-Modern-Amber', 'cursor-size': '24'}
            schema = 'org.gnome.desktop.interface'
            keys = subprocess.run(['gsettings', 'list-keys', schema], capture_output=True, text=True, check=True).stdout.splitlines()
            backup_dir = home / '.local/state/atelier'
            backup_dir.mkdir(parents=True, exist_ok=True)
            snapshot = {key: subprocess.run(['gsettings', 'get', schema, key], capture_output=True,
                                           text=True, check=True).stdout.strip() for key in preferences if key in keys}
            snapshot_path = backup_dir / ('gsettings.' + datetime.now().strftime('%Y%m%d%H%M%S%f') + '.json')
            snapshot_path.write_text(json.dumps(snapshot, indent=2) + '\n')
            print(f'GSettings backup: {snapshot_path}')
            for key, value in preferences.items():
                if key in keys:
                    subprocess.run(['gsettings', 'set', schema, key, value], check=True)
        if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE') and shutil.which('hyprctl'):
            hypr_config = config / 'hypr/hyprland.lua'
            if hypr_config.exists() and shutil.which('Hyprland'):
                verification = subprocess.run(['Hyprland', '--verify-config', '-c', str(hypr_config)],
                                              capture_output=True, text=True)
                if verification.returncode:
                    raise RuntimeError('Hyprland validation failed; no reload requested:\n' +
                                       verification.stdout + verification.stderr)
                print('Hyprland configuration verified.')
            subprocess.run(['hyprctl', 'reload'], check=True)
            subprocess.run(['hyprctl', 'setcursor', 'Bibata-Modern-Amber', '24'], check=True)
            errors = subprocess.run(['hyprctl', 'configerrors'], capture_output=True, text=True, check=True).stdout.strip()
            if errors:
                raise RuntimeError('Hyprland reported configuration errors after reload; inspect hyprctl configerrors')
        if os.environ.get('DBUS_SESSION_BUS_ADDRESS') and shutil.which('gdbus'):
            # Reload config in the existing process, preserving terminals/jobs.
            subprocess.run(['gdbus', 'call', '--session', '--dest', 'com.mitchellh.ghostty',
                            '--object-path', '/com/mitchellh/ghostty', '--method', 'org.gtk.Actions.Activate',
                            'reload-config', '[]', '{}'], capture_output=True)
    print('Atelier user theme installed. Open a new Fish shell; reopen GTK apps to refresh CSS.')
    print('VS Code may need Developer: Reload Window to discover the new local theme extension.')
    print('Root-owned ReGreet appearance is not installed by this command; see docs/theme.md.')


if __name__ == '__main__':
    main()
