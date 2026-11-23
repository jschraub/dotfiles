"""Machine-local keyring lifecycle; no password in argv, environment, IPC or logs."""
import argparse
import fcntl
import os
import subprocess
import sys

from credentials import preflight, private_directory, provision
from health import check
from migration import activate, refresh
from paths import Paths
from keyring_session import start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('preflight', 'provision', 'activate', 'status', 'start', 'refresh'))
    command = parser.parse_args().command
    paths = Paths.current()
    if command == 'start':
        start(paths)
        return
    if command == 'preflight':
        preflight()
        print('oo7 tools, systemd >=258 and TPM2 are available.')
        return
    if command == 'status':
        check()
        return
    if os.geteuid() == 0:
        raise ValueError('Run as the desktop account, not root')
    private_directory(paths.state)
    with (paths.state / 'setup.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'provision': provision, 'activate': activate, 'refresh': refresh}[command](paths)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Keyring operation failed: {error}', file=sys.stderr)
        raise SystemExit(1)
