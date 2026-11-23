"""Read-only checks of service ownership and lock state; never reads a secret."""
import json
from pathlib import Path
import subprocess


def bus(*arguments):
    result = subprocess.run(['busctl', '--user', '--timeout=5', '--json=short', *arguments],
                            capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)['data']
    # Method replies wrap arguments in a list; get-property returns a scalar.
    return data[0] if isinstance(data, list) else data


def check():
    pid = bus('call', 'org.freedesktop.DBus', '/org/freedesktop/DBus',
              'org.freedesktop.DBus', 'GetConnectionUnixProcessID', 's', 'org.freedesktop.secrets')
    if Path(f'/proc/{pid}/exe').resolve().name != 'oo7-daemon':
        raise ValueError('oo7 does not own org.freedesktop.secrets')
    collection = bus('call', 'org.freedesktop.secrets', '/org/freedesktop/secrets',
                     'org.freedesktop.Secret.Service', 'ReadAlias', 's', 'default')
    if collection == '/':
        raise ValueError('No default keyring collection was found')
    locked = bus('get-property', 'org.freedesktop.secrets', collection,
                 'org.freedesktop.Secret.Collection', 'Locked')
    if locked:
        raise ValueError('oo7 owns Secret Service, but the default keyring is still locked')
    print('oo7 owns Secret Service; the default keyring is unlocked. No secrets were read.')
