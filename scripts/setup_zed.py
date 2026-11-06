#!/usr/bin/env python3
"""User-only Zed configuration/default-editor setup; package install is separate."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess

from apply_theme import ROOT, configure_zed, link


def install(home, root=ROOT, config=None):
    config = config or home / '.config'
    for source in sorted((root / 'editor').rglob('*')):
        if source.is_file():
            link(source, home / source.relative_to(root / 'editor'))
    configure_zed(home, root, config)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-runtime', action='store_true', help='do not change the text/plain file association')
    args = parser.parse_args()
    subprocess.run(['python3', '-B', str(ROOT / 'scripts/render_theme.py'), '--check'], check=True)
    home = Path.home()
    config = Path(os.environ.get('XDG_CONFIG_HOME') or home / '.config')
    install(home, config=config)
    if not args.no_runtime and shutil.which('xdg-mime'):
        old = subprocess.run(['xdg-mime', 'query', 'default', 'text/plain'],
                             capture_output=True, text=True, check=True).stdout.strip()
        if old != 'atelier-editor.desktop':
            state = Path(os.environ.get('XDG_STATE_HOME') or home / '.local/state') / 'atelier'
            state.mkdir(parents=True, exist_ok=True)
            snapshot = state / ('editor-defaults.' + datetime.now().strftime('%Y%m%d%H%M%S%f') + '.json')
            snapshot.write_text(json.dumps({'text/plain': old}, indent=2) + '\n')
            print(f'File association backup: {snapshot}')
            subprocess.run(['xdg-mime', 'default', 'atelier-editor.desktop', 'text/plain'], check=True)
    print('Zed configured with Atelier Amber. Existing VS Code settings were left intact.')
    if not any(shutil.which(name) for name in ['zeditor', 'zed']):
        print('Zed is not installed yet. Run ./setup.sh zed; desktop-editor falls back to VS Code meanwhile.')


if __name__ == '__main__':
    main()
