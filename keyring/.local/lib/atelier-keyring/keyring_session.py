"""Non-blocking desktop startup policy; no fallback when the selected oo7 fails."""
import subprocess
import sys
import time

from health import wait_for_ready

WARNING = ('Stored credentials are unavailable. Run desktop-keyring status and '
           'inspect journalctl --user -b -u oo7-daemon.service. '
           'Keep your recovery password; do not delete your keyrings.')


def warn():
    print('Keyring unavailable. ' + WARNING, file=sys.stderr)
    # Hyprland starts the shell independently. Wait for its notification owner
    # rather than activating another notification daemon during session startup.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            owner = subprocess.run(
                ['busctl', '--user', '--timeout=1', 'call', 'org.freedesktop.DBus',
                 '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'NameHasOwner',
                 's', 'org.freedesktop.Notifications'],
                capture_output=True, text=True, check=True, timeout=1)
            if owner.stdout.strip() == 'b true':
                subprocess.run(['notify-send', '--app-name=Atelier', '--urgency=critical',
                                'Keyring unavailable', WARNING],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=True, timeout=3)
                return
        except (OSError, subprocess.SubprocessError):
            pass
        time.sleep(.5)


def start(paths):
    if not paths.selector.is_file() or paths.selector.read_text().strip() != 'oo7':
        subprocess.run(['gnome-keyring-daemon', '--start', '--components=secrets,pkcs11'], check=True)
        return
    try:
        subprocess.run(['systemctl', '--user', 'start', 'oo7-daemon.service'], check=True, timeout=20)
        wait_for_ready()
    except (OSError, ValueError, subprocess.SubprocessError):
        warn()
        # This helper is launched independently, never from the PAM login stack.
        raise ValueError('oo7 startup failed; desktop login is unaffected') from None
