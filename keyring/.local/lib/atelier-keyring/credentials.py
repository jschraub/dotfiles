"""Interactive password verification and TPM sealing, without plaintext files."""
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from paths import CREDENTIAL


def preflight():
    if os.geteuid() == 0:
        raise ValueError('Run as the desktop account, not root')
    for command in ('oo7-cli', 'systemd-creds', 'systemd-analyze', 'systemctl', 'busctl', 'dbus-run-session'):
        if not shutil.which(command):
            raise ValueError(f'Missing {command}; run ./setup.sh keyring first')
    if not os.access('/usr/lib/oo7-daemon', os.X_OK):
        raise ValueError('Missing /usr/lib/oo7-daemon; install the Arch/CachyOS oo7 package')
    version = subprocess.check_output(['systemctl', '--version'], text=True).split()[1]
    if int(version) < 258:
        raise ValueError('oo7 credential loading requires systemd 258 or newer')
    subprocess.run(['systemd-analyze', 'has-tpm2', '--quiet'], check=True)


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.stat().st_uid != os.getuid():
        raise ValueError(f'Not an owned directory: {path}')
    path.chmod(0o700)


def provision(paths):
    preflight()
    if not sys.stdin.isatty():
        raise ValueError('Provision from a terminal; the keyring password is entered privately')
    # Verify on a COPY. Never invoke a CLI list/lookup that can print real secrets.
    legacy = paths.keyrings / 'v1/login.keyring'
    migrated = legacy.is_file()
    if not migrated:
        legacy = paths.keyrings / 'login.keyring'
    if not legacy.is_file() or legacy.is_symlink():
        raise ValueError('Expected login.keyring; resolve the default keyring before provisioning')
    password = getpass.getpass('Current login KEYRING password (usually your login password): ').encode()
    if not password:
        raise ValueError('An empty keyring password is not supported')
    private_directory(paths.credential.parent)
    with tempfile.TemporaryDirectory(prefix='atelier-keyring-') as directory:
        temporary = Path(directory)
        destination = temporary / ('data/keyrings/v1' if migrated else 'data/keyrings')
        destination.mkdir(parents=True, mode=0o700)
        copied = destination / 'login.keyring'
        shutil.copy2(legacy, copied)
        verifier = Path(__file__).with_name('verify_password.py')
        verification = subprocess.run(['dbus-run-session', '--', sys.executable, '-B', str(verifier), str(temporary)],
                                      input=password, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        if verification.returncode:
            raise ValueError('oo7 could not decrypt a copy of login.keyring; no credential was replaced')
        fd, name = tempfile.mkstemp(prefix='.oo7-', dir=paths.credential.parent)
        os.close(fd)
        encrypted = Path(name)
        try:
            # Explicitly require TPM protection; never fall back to host-only/auto.
            subprocess.run(['systemd-creds', 'encrypt', '--user', '--with-key=host+tpm2',
                            '--tpm2-pcrs=7', f'--name={CREDENTIAL}', '-', str(encrypted)],
                           input=password, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(['systemd-creds', 'decrypt', '--user', f'--name={CREDENTIAL}',
                            str(encrypted), '/dev/null'], check=True)
            encrypted.chmod(0o600)
            os.replace(encrypted, paths.credential)
        finally:
            encrypted.unlink(missing_ok=True)
    print('Verified keyring password sealed with host+TPM2 protection and PCR 7.')
    print('Credential is local to this account and machine; keep your keyring password for recovery.')
