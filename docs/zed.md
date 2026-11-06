# Zed + Atelier Amber

Zed is the default code editor. VS Code is not uninstalled, and its settings,
extensions, workspaces and Remote-SSH setup are not deleted or converted.

## Install / carry to another machine

```sh
./setup.sh zed
./check-setup.sh zed
```

The default `./setup.sh all` includes Zed. On Arch/CachyOS it uses the repository's
`zed` package, not a curl installer or AUR build. If sudo authentication cannot be
provided in the agent's environment, install interactively:

```sh
sudo pacman -S --needed zed
./setup-zed.sh
```

`./setup-zed.sh` only configures user files; it doesn't install packages. It links
the generated theme and editor launcher, merges Zed settings with a timestamped
backup, and makes the launcher the `text/plain` default. Use `--no-runtime` to
skip the file association. The previous association is saved under
`~/.local/state/atelier/editor-defaults.TIMESTAMP.json` (or `XDG_STATE_HOME`).
Directories still open in Nautilus; other MIME associations are not changed.

## Desktop and terminal integration

- **Super+W** opens `desktop-editor`, preferring Arch's `zeditor`, then upstream's
  `zed`. It falls back to `code` while Zed is not installed.
- Fish and newly launched Hyprland applications receive `EDITOR` and `VISUAL`
  pointing to `desktop-editor --wait`, so Git and similar tools wait for editing.
  Existing shells need a new shell or an explicit config reload. An explicit
  Git `core.editor` setting still takes precedence; it is not overwritten.
- The application launcher includes **Zed (Atelier)**. Zed's native desktop entry
  may also appear after package installation.

## Theme and settings

`theme/palette.json` generates `zed/.config/zed/themes/atelier-amber.json` in
Zed's published theme-family format. It covers neutral UI/editor surfaces,
amber selections/focus, orange syntax accents, semantic diagnostics, collaboration
cursors and the same 16 ANSI colors used by Ghostty. It uses no marketplace theme
extension and doesn't depend on VS Code's theme.

The installer selects **Atelier Amber** in dark mode. Existing font choices,
VSCode keymap, agent settings, language tools and other preferences are preserved,
including JSONC comments. Missing defaults get Inter UI, CaskaydiaCove code text,
13px code font and the VSCode keymap. The writable `settings.json` is **not**
stowed into the repo; only the theme is linked. Secrets and machine-specific
settings never need to be copied into dotfiles.

`./setup-theme.sh` also updates the theme in existing Zed installations. For a
first theme load, open Zed and select **Atelier Amber** in the theme selector if
necessary. Project-specific theme overrides may take precedence.

## Verification and limitations

```sh
python3 scripts/render_theme.py --check
python3 -B -m unittest discover -s tests -p test_zed.py
```

Tests cover theme roles/ANSI colors, fresh installs, alternate config paths,
preservation/backups/idempotency and launcher selection/argument forwarding.
Actual Zed rendering requires the editor to be installed and a working Vulkan GPU.
No GPU driver, language extension, formatter, remote host, AI provider or credential
is changed by this migration. Zed does not use VS Code extensions directly.

References: [themes](https://zed.dev/docs/themes),
[theme schema](https://zed.dev/schema/themes/v0.2.0.json),
[Linux installation](https://zed.dev/docs/linux),
[CLI](https://zed.dev/docs/reference/cli.md).
