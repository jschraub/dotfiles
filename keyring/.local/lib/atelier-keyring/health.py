"""Read-only checks of service ownership and lock state; never reads a secret."""
import json
from pathlib import Path
import subprocess
import time


def bus(*arguments, timeout=5):
    result = subprocess.run(['busctl', '--user', '--timeout=5', '--json=short', *arguments],
                            capture_output=True, text=True, check=True, timeout=timeout)
    data = json.loads(result.stdout)['data']
    # Method replies wrap arguments in a list; get-property returns a scalar.
    return data[0] if isinstance(data, list) else data


def check(timeout=5):
    pid = bus('call', 'org.freedesktop.DBus', '/org/freedesktop/DBus',
              'org.freedesktop.DBus', 'GetConnectionUnixProcessID', 's', 'org.freedesktop.secrets', timeout=timeout)
    if Path(f'/proc/{pid}/exe').resolve().name != 'oo7-daemon':
        raise ValueError('oo7 does not own org.freedesktop.secrets')
    collection = bus('call', 'org.freedesktop.secrets', '/org/freedesktop/secrets',
                     'org.freedesktop.Secret.Service', 'ReadAlias', 's', 'default', timeout=timeout)
    if collection == '/':
        raise ValueError('No default keyring collection was found')
    locked = bus('get-property', 'org.freedesktop.secrets', collection,
                 'org.freedesktop.Secret.Collection', 'Locked', timeout=timeout)
    if locked:
        raise ValueError('oo7 owns Secret Service, but the default keyring is still locked')
    print('oo7 owns Secret Service; the default keyring is unlocked. No secrets were read.')


def wait_for_ready(timeout=15):
    """Wait for ownership AND unlock, without changing providers or reading secrets."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('Timed out waiting for oo7 to own Secret Service and unlock the default keyring')
        try:
            # A probe has three sequential bus calls. Bound their combined wait.
            check(timeout=min(1, remaining / 3))
            return
        except (OSError, ValueError, subprocess.SubprocessError):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(.25, remaining))
