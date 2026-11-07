#!/usr/bin/env python3
"""Remove only this checkout's retired UI links; never real/foreign configs."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RETIRED = ('waybar', 'swaync', 'wofi', 'wlogout', 'fuzzel', 'hyprpaper', 'polkit-gnome')


def retired_links(home, config, root=ROOT):
    sources = [root / name for name in ('waybar', 'wofi', 'wlogout')]
    sources += [root / 'hyprland-common/.config/swaync', root / 'hyprland-common/.local/bin/desktop-wallpaper']
    sources += [root / 'hyprland-common/.config/hypr/scripts' / name
                for name in ('keybindings.css', 'atelier-colors.json')]
    candidates = [config / name for name in ('waybar', 'wofi', 'wlogout', 'fuzzel', 'swaync')]
    candidates += [config / 'hypr/scripts' / name for name in ('keybindings.css', 'atelier-colors.json')]
    candidates += [home / '.local/bin' / name for name in (
        'keep-awake.sh', 'waybar-popup.py', 'network-menu.sh', 'vpn-status.sh',
        'wlogout-centered.sh', 'desktop-wallpaper')]
    found = []
    def visit(path):
        if path.is_symlink():
            target = path.resolve()
            if any(target == source or source in target.parents for source in sources):
                found.append(path)
        elif path.is_dir():
            for child in path.iterdir():
                visit(child)
    for path in candidates:
        visit(path)
    return found


def remove_owned_mask(runtime):
    marker = runtime / 'dotfiles-atelier-swaync-mask'
    unit = runtime / 'systemd/user/swaync.service'
    if marker.is_symlink() or not marker.is_file():
        return False
    if unit.is_symlink() and os.readlink(unit) == '/dev/null':
        unit.unlink()
    marker.unlink()
    return True


def main():
    # Never remove the reactivation guard while the retired server is installed.
    for package in RETIRED:
        if subprocess.run(['pacman', '-Q', package], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0:
            raise SystemExit(f'{package} is still installed; run cleanup-atelier.sh first.')
    home = Path.home()
    config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    for path in retired_links(home, config):
        path.unlink()
        print(f'Removed managed link: {path}')
    if remove_owned_mask(runtime):
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    selector = config / 'dotfiles/desktop-shell'
    if not selector.is_symlink() and selector.is_file() and selector.read_text().strip() == 'quickshell':
        selector.unlink()


if __name__ == '__main__':
    main()
