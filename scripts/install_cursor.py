#!/usr/bin/env python3
"""Install pinned upstream Bibata cursor assets per-user, without root or vendoring."""
import argparse
from datetime import datetime
import hashlib
from pathlib import Path
import os
import tarfile
import tempfile
import urllib.request

THEME = 'Bibata-Modern-Amber'
VERSION = '2.0.7'
SHA256 = '58b7ac00ed3cb45acb6b917cb9807a553873f1cca5c91348c4abaebe638e5884'
URL = f'https://github.com/ful1e5/Bibata_Cursor/releases/download/v{VERSION}/{THEME}.tar.xz'


def install(data, cache, archive=None):
    destination = data / 'icons' / THEME
    marker = destination / '.atelier-sha256'
    if not destination.is_symlink() and marker.is_file() and marker.read_text().strip() == SHA256 \
            and (destination / 'cursors/left_ptr').is_file():
        return destination
    if archive is None:
        cache.mkdir(parents=True, exist_ok=True)
        archive = cache / f'{THEME}-{VERSION}.tar.xz'
        if not archive.exists():
            request = urllib.request.Request(URL, headers={'User-Agent': 'Atelier-dotfiles'})
            with urllib.request.urlopen(request, timeout=60) as response:
                contents = response.read(8 * 1024 * 1024)
            if hashlib.sha256(contents).hexdigest() != SHA256:
                raise ValueError('Cursor download checksum mismatch; nothing installed')
            archive.write_bytes(contents)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError('Cursor archive checksum mismatch; nothing installed')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.atelier-cursor-', dir=destination.parent) as staging:
        with tarfile.open(archive) as bundle:
            if any(Path(member.name).parts[0] != THEME for member in bundle.getmembers()):
                raise ValueError('Unexpected cursor archive layout')
            bundle.extractall(staging, filter='data')
        unpacked = Path(staging) / THEME
        if not (unpacked / 'cursors/left_ptr').is_file():
            raise ValueError('Cursor archive has no default pointer')
        (unpacked / '.atelier-sha256').write_text(SHA256 + '\n')
        if destination.exists() or destination.is_symlink():
            backup = destination.with_name(THEME + '.backup-' + datetime.now().strftime('%Y%m%d%H%M%S%f'))
            destination.rename(backup)
            print(f'Cursor backup: {backup}')
        unpacked.rename(destination)
    print(f'Installed cursor: {destination}')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='use an already-downloaded archive (checksum still enforced)')
    args = parser.parse_args()
    home = Path.home()
    install(Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share'),
            Path(os.environ.get('XDG_CACHE_HOME') or home / '.cache') / 'atelier/cursors', args.archive)


if __name__ == '__main__':
    main()
