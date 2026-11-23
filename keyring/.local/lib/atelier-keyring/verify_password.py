"""Validate a copied keyring on a PRIVATE D-Bus session, never the live provider."""
import os
from pathlib import Path
import subprocess
import sys
import time

from health import check


def verify(root, daemon='/usr/lib/oo7-daemon'):
    # dbus-run-session supplies a private bus. Isolate all daemon discovery paths.
    environment = dict(os.environ, HOME=str(root), XDG_DATA_HOME=str(root / 'data'),
                       XDG_CONFIG_HOME=str(root / 'config'), XDG_RUNTIME_DIR=str(root / 'runtime'))
    (root / 'runtime').mkdir(mode=0o700)
    process = subprocess.Popen([daemon, '--login'], stdin=sys.stdin.buffer,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and process.poll() is None:
            try:
                check()
                return 0
            except (ValueError, OSError, subprocess.SubprocessError):
                time.sleep(.1)
        return 1
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == '__main__':
    raise SystemExit(verify(Path(sys.argv[1])))
