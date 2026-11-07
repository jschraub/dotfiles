#!/usr/bin/env python3
"""Stage root-owned Atelier authentication UI; activate greetd only when explicit."""
import argparse
import fcntl
from datetime import datetime
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tempfile
import tomllib

SOURCE = Path(__file__).resolve().parents[1]
FILES = ('Theme.qml', 'Label.qml', 'ActionButton.qml', 'SearchField.qml',
         'AccessIdentity.qml', 'AccessCard.qml', 'AccessScene.qml', 'LockController.qml',
         'GreeterController.qml', 'access_identity.py', 'lock.qml', 'greeter.qml')
OLD = 'dbus-run-session start-hyprland -- -c /etc/greetd/hyprland.lua'
NEW = 'dbus-run-session start-hyprland -- -c /etc/greetd/atelier-hyprland.lua'


def verify_config(config):
    # sudo intentionally strips the caller's runtime environment. Even config
    # verification requires XDG_RUNTIME_DIR; never point a privileged verifier
    # at the user's live Wayland/IPC sockets or session bus.
    with tempfile.TemporaryDirectory(prefix='atelier-verify-') as runtime:
        directory = Path(runtime)
        validation = directory / 'hyprland.lua'
        validation.write_bytes(config.read_bytes())
        validation.chmod(0o600)
        credentials = {}
        if os.geteuid() == 0:
            greeter = pwd.getpwnam('greeter')
            os.chown(directory, greeter.pw_uid, greeter.pw_gid)
            os.chown(validation, greeter.pw_uid, greeter.pw_gid)
            credentials = {'user': greeter.pw_uid, 'group': greeter.pw_gid, 'extra_groups': []}
        environment = dict(os.environ, XDG_RUNTIME_DIR=runtime, HOME=runtime,
                           XDG_CONFIG_HOME=str(directory / 'config'),
                           XDG_CACHE_HOME=str(directory / 'cache'), XDG_DATA_HOME=str(directory / 'data'))
        for name in ('WAYLAND_DISPLAY', 'WAYLAND_SOCKET', 'DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE',
                     'DBUS_SESSION_BUS_ADDRESS', 'NOTIFY_SOCKET'):
            environment.pop(name, None)
        subprocess.run(['Hyprland', '--verify-config', '-c', str(validation)],
                       env=environment, check=True, **credentials)


def greeter_config(source):
    old = 'hl.exec_cmd("regreet; hyprctl dispatch \'hl.dsp.exit()\'")'
    new = 'hl.exec_cmd("/usr/bin/qs -p /etc/atelier/access/greeter.qml; hyprctl dispatch \'hl.dsp.exit()\'")'
    if source.count(old) != 1:
        raise ValueError('Greeter startup changed; review its compositor config before installing')
    return source.replace(old, new)


def activate_config(source):
    parsed = tomllib.loads(source)
    session = parsed.get('default_session', {})
    if session.get('user') != 'greeter' or session.get('command') not in (OLD, NEW):
        raise ValueError('Unrecognized greetd session policy; refusing to overwrite local configuration')
    # Change only the known command within default_session, preserving VT/user
    # and any unrelated settings/comments. No login/PAM/session policy changes.
    sections = re.split(r'(?m)(^\[.*\]\s*$)', source)
    for index, section in enumerate(sections):
        if section.strip() == '[default_session]':
            sections[index + 1], count = re.subn(r'(?m)^command\s*=\s*"[^"\n]*"',
                                                f'command = "{NEW}"', sections[index + 1])
            if count != 1:
                raise ValueError('Ambiguous greetd command')
            return ''.join(sections)
    raise ValueError('Missing greetd default session')


class Installer:
    def __init__(self, root=Path('/'), source=SOURCE):
        self.root = root
        self.source = source

    def destination(self, path):
        return self.root / path.lstrip('/')

    def directory(self, path):
        target = self.destination(path)
        # Never traverse a pre-existing directory symlink during privileged copy.
        for part in [target, *target.parents]:
            if part == self.root.parent:
                break
            if part.is_symlink():
                raise ValueError(f'Refusing symlink directory: {part}')
            if part == self.root:
                break
        existed = target.exists()
        target.mkdir(parents=True, exist_ok=True)
        managed = path.startswith('/etc/atelier') or path.startswith('/usr/share/atelier') or path == '/etc/greetd'
        if not existed or managed:
            target.chmod(0o755)
            if os.geteuid() == 0:
                os.chown(target, 0, 0)
        elif os.geteuid() == 0:
            metadata = target.stat()
            if metadata.st_uid != 0 or metadata.st_mode & 0o022:
                raise ValueError(f'Untrusted shared system directory: {target}')
        return target

    def write(self, path, contents, mode=0o644):
        destination = self.destination(path)
        self.directory(str(Path(path).parent))
        if destination.is_symlink():
            raise ValueError(f'Refusing symlink configuration: {destination}')
        if destination.exists() and destination.read_bytes() != contents:
            backup = destination.with_name(destination.name + '.pre-atelier.' + datetime.now().strftime('%Y%m%d%H%M%S%f'))
            shutil.copy2(destination, backup)
        fd, temporary = tempfile.mkstemp(prefix='.atelier-', dir=destination.parent)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(contents)
                os.fchmod(output.fileno(), mode)
                if os.geteuid() == 0:
                    os.fchown(output.fileno(), 0, 0)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def install(self, uid):
        if self.root != Path('/'):
            return self._install(uid)
        descriptors = []
        try:
            # The installed bundle is shared. Protect other logged-in accounts'
            # lock surfaces too, not just the account receiving an avatar.
            for runtime in Path('/run/user').iterdir():
                if not runtime.name.isdecimal() or not runtime.is_dir():
                    continue
                descriptor = os.open(runtime / 'dotfiles-atelier-lock.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                descriptors.append(descriptor)
                os.fchown(descriptor, int(runtime.name), -1)
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError('Unlock every native-locked session before updating its authentication UI') from None
            return self._install(uid)
        finally:
            for descriptor in descriptors:
                os.close(descriptor)

    def _install(self, uid):
        if uid < 1000 or uid >= 65534:
            raise ValueError('Choose a regular local account for the preserved avatar')
        self.directory('/etc/atelier')
        self.directory('/etc/atelier/access')
        self.directory('/usr/share/atelier')
        self.directory('/usr/share/atelier/access')
        self.directory('/usr/share/atelier/access/avatars')
        ui = self.source / 'quickshell/.config/quickshell/atelier'
        # Validate the generated greeter config BEFORE writing anything used by greetd.
        generated = greeter_config((self.source / 'greetd-setup/etc/greetd/hyprland.lua').read_text())
        with tempfile.TemporaryDirectory(prefix='atelier-access-') as temporary:
            config = Path(temporary) / 'hyprland.lua'
            config.write_text(generated)
            verify_config(config)
        for name in FILES:
            self.write('/etc/atelier/access/' + name, (ui / name).read_bytes())
        self.write('/etc/atelier/access/qmldir', (self.source / 'auth-setup/qmldir').read_bytes())
        self.write('/usr/share/atelier/access/background.jpg',
                   (self.source / 'backgrounds/.config/backgrounds/tolkien/balrog.jpg').read_bytes())
        self.write(f'/usr/share/atelier/access/avatars/{uid}.png',
                   (self.source / 'greetd-setup/greeter-avatar.png').read_bytes())
        for name in ('atelier-lock', 'atelier-fingerprint'):
            self.write('/etc/pam.d/' + name, (self.source / 'auth-setup/pam' / name).read_bytes())
        self.write('/etc/greetd/atelier-hyprland.lua', generated.encode())

    def activate(self):
        required = ('/etc/atelier/access/greeter.qml', '/etc/greetd/atelier-hyprland.lua',
                    '/usr/share/atelier/access/background.jpg')
        if not all(self.destination(path).is_file() for path in required):
            raise ValueError('Stage the authentication UI first')
        path = self.destination('/etc/greetd/config.toml')
        if path.is_symlink():
            raise ValueError('Refusing a symlink greetd configuration')
        source = path.read_text()
        updated = activate_config(source)
        backup = self.destination('/etc/greetd/config.toml.before-atelier')
        if backup.is_symlink():
            raise ValueError('Refusing a symlink greeter recovery backup')
        if not backup.exists():
            self.write('/etc/greetd/config.toml.before-atelier', source.encode(), 0o600)
        verify_config(self.destination('/etc/greetd/atelier-hyprland.lua'))
        self.write('/etc/greetd/config.toml', updated.encode(), 0o640)
        self.write('/etc/atelier/access/greeter-selected', b'atelier\n')
        print('Atelier greeter selected for the NEXT login. greetd was NOT restarted.')
        print('Recovery from a TTY: sudo cp -a /etc/greetd/config.toml.before-atelier /etc/greetd/config.toml')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account', help='regular account whose existing avatar is installed')
    parser.add_argument('--activate-greeter', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run through sudo; no live authentication or session restart is performed')
    installer = Installer()
    if args.activate_greeter:
        installer.activate()
    else:
        if not args.account:
            parser.error('--account is required for staging')
        installer.install(pwd.getpwnam(args.account).pw_uid)
        print('Root-owned UI/PAM/assets staged. Live login and lock selection are unchanged.')


if __name__ == '__main__':
    main()
