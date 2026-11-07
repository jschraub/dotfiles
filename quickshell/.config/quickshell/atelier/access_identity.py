#!/usr/bin/env python3
"""Public account metadata only. Never reads credentials or starts authentication."""
import json
import os
from pathlib import Path
import pwd
import sys

ASSETS = Path('/usr/share/atelier/access')


def account(entry, *, preview=False):
    # AccountsService's standard per-user icon location is visible to greeters
    # without opening a user's private home. Installed avatars are UID-specific.
    candidates = [Path('/var/lib/AccountsService/icons') / entry.pw_name,
                  ASSETS / 'avatars' / f'{entry.pw_uid}.png']
    if preview and entry.pw_uid == os.getuid():
        config = Path(os.environ.get('XDG_CONFIG_HOME') or Path(entry.pw_dir) / '.config')
        candidates += [config / 'avatars/gandalf_the_grey_by_numediteur_dhhugwm-pre.jpg']
    icon = next((str(path) for path in candidates if path.is_file() and os.access(path, os.R_OK)), '')
    return {'user': entry.pw_name, 'uid': entry.pw_uid,
            'name': entry.pw_gecos.split(',')[0] or entry.pw_name, 'avatar': icon}


def identities(mode, *, preview=False):
    if mode == 'lock':
        entries = [pwd.getpwuid(os.getuid())]
    elif mode == 'greeter':
        entries = sorted((entry for entry in pwd.getpwall()
                          if 1000 <= entry.pw_uid < 65534 and entry.pw_shell
                          and Path(entry.pw_shell).name not in ('nologin', 'false')),
                         key=lambda entry: entry.pw_name)
    else:
        raise ValueError('Unknown access mode')
    background = ASSETS / 'background.jpg'
    if preview:
        background = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'backgrounds/tolkien/balrog.jpg'
    return {'users': [account(entry, preview=preview) for entry in entries], 'background': str(background)}


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'lock'
    print(json.dumps(identities(mode, preview='--preview' in sys.argv[2:])))
