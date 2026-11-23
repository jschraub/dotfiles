"""Reversible provider selection with private backups and exact-file rollback."""
import base64
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess

from credentials import preflight, private_directory
from health import check

TEMPLATES = Path(__file__).resolve().parents[2] / 'share/atelier-keyring'


def files(paths):
    return {
        paths.data / 'dbus-1/services/org.freedesktop.secrets.service': 'org.freedesktop.secrets.service',
        paths.config / 'systemd/user/oo7-daemon.service.d/20-atelier-credentials.conf': 'oo7-credentials.conf',
        paths.config / 'systemd/user/gnome-keyring-daemon.service.d/20-atelier-pkcs11.conf': 'gnome-pkcs11.conf',
        paths.config / 'autostart/gnome-keyring-secrets.desktop': 'gnome-keyring-secrets.desktop',
        paths.selector: None,
    }


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f'Refusing to replace symlink: {path}')
    temporary = path.with_name(path.name + '.atelier-new')
    # Exclusive creation avoids following a stale or pre-created symlink.
    with temporary.open('xb') as output:
        try:
            os.chmod(temporary, 0o600)
            output.write(content)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def systemctl(*arguments, check=True):
    return subprocess.run(['systemctl', '--user', *arguments], check=check)


def enabled(unit):
    return subprocess.run(['systemctl', '--user', 'is-enabled', '--quiet', unit]).returncode == 0


def backup(paths):
    private_directory(paths.state)
    manifest = paths.state / 'migration.json'
    if manifest.exists():
        raise ValueError('A migration record already exists; use status or rollback before migrating again')
    # Reject symlinks in the data being backed up rather than copying outside it.
    if paths.keyrings.is_symlink() or any(p.is_symlink() for p in paths.keyrings.rglob('*')):
        raise ValueError('Resolve symlinks in the keyring directory before migration')
    destination = paths.state / ('backup-' + datetime.now().strftime('%Y%m%d%H%M%S%f'))
    destination.mkdir(mode=0o700)
    if paths.keyrings.exists():
        shutil.copytree(paths.keyrings, destination / 'keyrings')
        for item in (destination / 'keyrings').rglob('*'):
            item.chmod(0o700 if item.is_dir() else 0o600)
    previous = {}
    for path in files(paths):
        if path.is_symlink():
            raise ValueError(f'Resolve local symlink before selecting oo7: {path}')
        previous[str(path)] = base64.b64encode(path.read_bytes()).decode() if path.exists() else None
    record = {'backup': str(destination), 'files': previous,
              'oo7_enabled': enabled('oo7-daemon.service')}
    write(manifest, json.dumps(record, indent=2).encode())
    return record


def rollback(paths):
    manifest = paths.state / 'migration.json'
    record = json.loads(manifest.read_text())
    # Only restore the paths the current program owns, never arbitrary manifest paths.
    if set(record['files']) != {str(path) for path in files(paths)}:
        raise ValueError('Migration record paths do not match this account')
    systemctl('stop', 'oo7-daemon.service', check=False)
    if not record['oo7_enabled']:
        systemctl('disable', 'oo7-daemon.service', check=False)
    for name, content in record['files'].items():
        path = Path(name)
        if path.is_symlink():
            raise ValueError(f'Refusing to overwrite local symlink during rollback: {path}')
        if content is None:
            path.unlink(missing_ok=True)
        else:
            write(path, base64.b64decode(content))
    systemctl('daemon-reload')
    systemctl('restart', 'gnome-keyring-daemon.service')
    manifest.rename(manifest.with_name('migration-rolled-back-' + datetime.now().strftime('%Y%m%d%H%M%S%f') + '.json'))
    print('Previous provider configuration restored. New oo7 data and the encrypted credential were preserved.')
    print('Backup:', record['backup'])


def activate(paths):
    preflight()
    if not paths.credential.is_file() or paths.credential.is_symlink():
        raise ValueError('Provision the TPM credential first')
    if paths.credential.stat().st_mode & 0o077:
        raise ValueError('The TPM credential must have mode 600')
    # A failed TPM check must not stop the currently working Secret Service.
    subprocess.run(['systemd-creds', 'decrypt', '--user', str(paths.credential), '/dev/null'], check=True)
    for template in files(paths).values():
        if template is not None and not (TEMPLATES / template).is_file():
            raise ValueError('Keyring templates are missing; run ./setup.sh keyring')
    record = backup(paths)
    try:
        for path, template in files(paths).items():
            if path == paths.selector:
                continue
            write(path, (TEMPLATES / template).read_bytes())
        systemctl('daemon-reload')
        # Restart with PKCS#11 only, relinquishing org.freedesktop.secrets.
        systemctl('restart', 'gnome-keyring-daemon.service')
        systemctl('enable', '--now', 'oo7-daemon.service')
        check()
        write(paths.selector, b'oo7\n')
        record['installed'] = {str(path): base64.b64encode(path.read_bytes()).decode() for path in files(paths)}
        write(paths.state / 'migration.json', json.dumps(record, indent=2).encode())
    except BaseException:
        rollback(paths)
        raise
    print('oo7 selected. Original keyrings backed up at:', record['backup'])
    print('Test a fresh login and suspend/resume; retain the backup and recovery password.')


def refresh(paths):
    """Refresh selected provider configuration, never provision or restart services."""
    if not paths.selector.is_file() or paths.selector.read_text().strip() != 'oo7':
        return
    manifest = paths.state / 'migration.json'
    record = json.loads(manifest.read_text())
    for path in files(paths):
        expected = record.get('installed', {}).get(str(path))
        if path.is_symlink() or expected is None or path.read_bytes() != base64.b64decode(expected):
            raise ValueError(f'Local keyring configuration differs; review before updating: {path}')
    for path, template in files(paths).items():
        if template:
            write(path, (TEMPLATES / template).read_bytes())
    record['installed'] = {str(path): base64.b64encode(path.read_bytes()).decode() for path in files(paths)}
    write(manifest, json.dumps(record, indent=2).encode())
    systemctl('daemon-reload')
