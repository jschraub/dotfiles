"""Read-only checks for known consumers of GNOME's obsolete PKCS#11 provider."""
from pathlib import Path
import shutil


def available():
    return shutil.which('gnome-keyring-daemon') is not None


def consumers(config, home=None):
    home = Path.home() if home is None else home
    result = [name for name in ('geary', 'midori') if shutil.which(name)]
    registrations = set()
    for directory in (config / 'zen', config / 'mozilla', home / '.mozilla',
                      home / '.thunderbird', home / '.pki'):
        if directory.is_dir():
            registrations.update(directory.rglob('pkcs11.txt'))
    modules = config / 'pkcs11/modules'
    if modules.is_dir():
        registrations.update(modules.glob('*.module'))
    registrations.add(home / '.ssh/config')
    for path in sorted(registrations):
        if path.is_file() and 'gnome-keyring-pkcs11' in path.read_text():
            result.append(str(path))
    return result
