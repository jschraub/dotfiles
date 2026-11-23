"""One-way oo7 selection with transactional cleanup if initial activation fails."""
import base64
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess

from credentials import preflight, private_directory
from health import wait_for_ready
from legacy_gnome import available as legacy_available, consumers as gnome_consumers

TEMPLATES = Path(__file__).resolve().parents[2] / 'share/atelier-keyring'
GNOME_UNITS = ('gnome-keyring-daemon.service', 'gnome-keyring-daemon.socket')


def files(paths):
    return {
        paths.data / 'dbus-1/services/org.freedesktop.secrets.service': 'org.freedesktop.secrets.service',
        paths.config / 'systemd/user/oo7-daemon.service.d/20-atelier-credentials.conf': 'oo7-credentials.conf',
        # A regular zero-byte unit file is a systemd mask, without a symlink
        # that could hide or overwrite another user's configuration.
        paths.config / 'systemd/user/gnome-keyring-daemon.service': 'masked-unit',
        paths.config / 'systemd/user/gnome-keyring-daemon.socket': 'masked-unit',
        paths.config / 'autostart/gnome-keyring-secrets.desktop': 'gnome-keyring-secrets.desktop',
        paths.config / 'autostart/gnome-keyring-pkcs11.desktop': 'gnome-keyring-pkcs11.desktop',
        paths.config / 'pkcs11/modules/gnome-keyring.module': 'gnome-keyring.module',
        paths.selector: None,
    }


def legacy_dropin(paths):
    return paths.config / 'systemd/user/gnome-keyring-daemon.service.d/20-atelier-pkcs11.conf'


def validate_record(paths, record):
    known = {str(path) for path in files(paths)} | {str(legacy_dropin(paths))}
    baseline = {str(paths.selector), str(paths.data / 'dbus-1/services/org.freedesktop.secrets.service'),
                str(paths.config / 'systemd/user/oo7-daemon.service.d/20-atelier-credentials.conf'),
                str(paths.config / 'autostart/gnome-keyring-secrets.desktop')}
    if not baseline.issubset(record['files']) or not set(record['files']).issubset(known):
        raise ValueError('Migration record paths do not match this account')
    if not set(record.get('installed', {})).issubset(known):
        raise ValueError('Installed migration record paths do not match this account')
    if record.get('installed') and not baseline.issubset(record['installed']):
        raise ValueError('Installed migration record is incomplete')


def require_no_gnome_consumers(paths):
    found = gnome_consumers(paths.config)
    if found:
        raise ValueError('GNOME PKCS#11 consumers need review before disabling it: ' + ', '.join(found))


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
        raise ValueError('A migration record already exists; inspect status and the record before retrying activation')
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
              'oo7_enabled': enabled('oo7-daemon.service'),
              'gnome_enabled': {unit: enabled(unit) for unit in GNOME_UNITS}}
    write(manifest, json.dumps(record, indent=2).encode())
    return record


def _restore_failed_activation(paths, record):
    """Undo only the activation currently in progress, not a completed migration."""
    manifest = paths.state / 'migration.json'
    validate_record(paths, record)
    systemctl('stop', 'oo7-daemon.service', check=False)
    if not record['oo7_enabled']:
        systemctl('disable', 'oo7-daemon.service', check=False)
    for name, content in record['files'].items():
        path = Path(name)
        if path.is_symlink():
            raise ValueError(f'Refusing to overwrite local symlink after failed activation: {path}')
        if content is None:
            path.unlink(missing_ok=True)
        else:
            write(path, base64.b64decode(content))
    systemctl('daemon-reload')
    for unit, was_enabled in record.get('gnome_enabled', {}).items():
        if unit in GNOME_UNITS:
            systemctl('enable' if was_enabled else 'disable', unit, check=False)
    if legacy_available():
        systemctl('restart', 'gnome-keyring-daemon.service')
    manifest.rename(manifest.with_name('migration-failed-' + datetime.now().strftime('%Y%m%d%H%M%S%f') + '.json'))
    print('Activation failed; pre-activation provider configuration restored. Keyring data and the encrypted credential were preserved.')
    print('Backup:', record['backup'])


def activate(paths):
    preflight()
    require_no_gnome_consumers(paths)
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
        systemctl('disable', '--now', *GNOME_UNITS, check=False)
        for path, template in files(paths).items():
            if path == paths.selector:
                continue
            write(path, (TEMPLATES / template).read_bytes())
        systemctl('daemon-reload')
        systemctl('enable', '--now', 'oo7-daemon.service')
        wait_for_ready()
        write(paths.selector, b'oo7\n')
        record['installed'] = {str(path): base64.b64encode(path.read_bytes()).decode() for path in files(paths)}
        write(paths.state / 'migration.json', json.dumps(record, indent=2).encode())
    except BaseException:
        _restore_failed_activation(paths, record)
        raise
    print('oo7 selected. Original keyrings backed up at:', record['backup'])
    print('Test a fresh login and suspend/resume; retain the backup and recovery password.')


def refresh(paths):
    """Refresh configuration and retire legacy GNOME, without restarting oo7."""
    if not paths.selector.is_file() or paths.selector.read_text().strip() != 'oo7':
        return
    manifest = paths.state / 'migration.json'
    record = json.loads(manifest.read_text())
    validate_record(paths, record)
    installed = record.get('installed', {})
    for name, expected in installed.items():
        path = Path(name)
        if path.is_symlink() or not path.is_file() or path.read_bytes() != base64.b64decode(expected):
            raise ValueError(f'Local keyring configuration differs; review before updating: {path}')
    retiring = str(legacy_dropin(paths)) in installed
    if retiring:
        require_no_gnome_consumers(paths)
        # Extend the original migration record BEFORE adding files or stopping
        # units. Preserve the old drop-in's pre-migration configuration metadata.
        for path, template in files(paths).items():
            if str(path) not in record['files']:
                if path.is_symlink() or (path.exists() and path.read_bytes() != (TEMPLATES / template).read_bytes()):
                    raise ValueError(f'Local keyring configuration differs; review before updating: {path}')
                record['files'][str(path)] = base64.b64encode(path.read_bytes()).decode() if path.exists() else None
        record['gnome_enabled'] = {unit: enabled(unit) for unit in GNOME_UNITS}
        write(manifest, json.dumps(record, indent=2).encode())
        systemctl('disable', '--now', *GNOME_UNITS, check=False)
        legacy_dropin(paths).unlink()
    elif set(installed) != {str(path) for path in files(paths)}:
        raise ValueError('Incomplete keyring migration record; restore or review it before updating')
    for path, template in files(paths).items():
        if template:
            write(path, (TEMPLATES / template).read_bytes())
    record['installed'] = {str(path): base64.b64encode(path.read_bytes()).decode() for path in files(paths)}
    write(manifest, json.dumps(record, indent=2).encode())
    systemctl('daemon-reload')
    if retiring:
        print('Unused GNOME PKCS#11 integration retired; oo7 and all stored keyrings were preserved.')
