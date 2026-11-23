"""Machine-local locations; credentials and keyrings never live in Stow."""
from dataclasses import dataclass
import os
from pathlib import Path

CREDENTIAL = 'oo7.keyring-encryption-password'


@dataclass(frozen=True)
class Paths:
    config: Path
    data: Path
    state: Path

    @classmethod
    def current(cls):
        home = Path.home()
        return cls(Path(os.environ.get('XDG_CONFIG_HOME') or home / '.config'),
                   Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share'),
                   Path(os.environ.get('XDG_STATE_HOME') or home / '.local/state') / 'atelier/keyring')

    @property
    def credential(self):
        return self.config / 'credstore.encrypted' / CREDENTIAL

    @property
    def selector(self):
        return self.config / 'dotfiles/keyring'

    @property
    def keyrings(self):
        return self.data / 'keyrings'
