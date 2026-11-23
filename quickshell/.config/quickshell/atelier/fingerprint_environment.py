"""Filesystem boundary for shared fingerprint policy and actual kernel lid state."""
import os
from pathlib import Path


def policy(environment=None, home=None):
    environment = os.environ if environment is None else environment
    if environment.get('ATELIER_FINGERPRINT') == '0':
        return 'off'
    value = environment.get('HYPRLOCK_FINGERPRINT')
    if not value:
        config = Path(environment.get('XDG_CONFIG_HOME') or (Path.home() if home is None else home) / '.config')
        try:
            value = (config / 'dotfiles/hyprlock-fingerprint').read_text().strip()
        except FileNotFoundError:
            value = 'auto'
        except OSError:
            value = 'off'
    return value if value in ('auto', 'on', 'off') else 'off'


def lid_closed(directory=Path('/proc/acpi/button/lid')):
    try:
        return any('closed' in path.read_text() for path in directory.glob('*/state'))
    except OSError:
        return True
