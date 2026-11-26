# Routine desktop updates

After initial setup, run as your normal desktop user:

```sh
cd ~/dotfiles
./update.sh --dry-run  # local plan, generated-theme/config checks, Stow simulation
./update.sh --check    # also audit the installed configuration
./update.sh            # review, fetch/fast-forward, review the plan, apply and audit
./update.sh --non-interactive  # routine updates without confirmation/authentication prompts
```

`upall` now calls `update.sh` after its repository/AUR/Flatpak updates, before
refreshing Cachy-Update. It passes `--non-interactive`, skipping routine confirmations
and disabling subprocess stdin and Git/SSH authentication prompts. If new
dependencies or a root-owned authentication refresh are required, it stops with
instructions to run `./update.sh` interactively; it never grants unattended
approval for privileged changes. A package-update failure skips desktop deployment; a desktop-update
failure is included in `upall`'s final failure summary. Deferred individual AUR
builds retain their existing behavior. The checkout is discovered from the linked
Fish function, or overridden with `DOTFILES_DIR`. The checkout-owned updater is
**never** run through the passwordless package gate; that policy is unchanged.

## Machine-local custom updaters

After the desktop-update step, `upall` looks for:

```text
${XDG_CONFIG_HOME:-$HOME/.config}/upall/custom.fish
```

If absent, the step is skipped. If present, it runs as the current user in a
separate `fish --no-config` process. It is not sourced into your interactive
shell, needs no executable bit, and does not run during Fish startup. A broken
symlink, unreadable script or nonzero exit is reported as `custom` in the final
failure summary. Custom updates still run after earlier updater failures, and
Cachy-Update's final refresh still runs if the custom script fails.

This file lives **outside the Stow packages**. Do not add it under
`fish/.config`: its commands belong to one machine, not every machine that uses
these dotfiles. Machines without custom software do not need the file. Hooks can
use a custom `XDG_CONFIG_HOME` even though the desktop updater itself requires
the standard layout.

Write ordinary Fish commands, check whether their software is installed, and
track failures so later commands still run:

```fish
set -l failed 0
if test -x "$HOME/.local/bin/some-app-updater"
    "$HOME/.local/bin/some-app-updater"
    or set failed 1
end
# More independent updater commands can follow.
exit $failed
```

The hook inherits exported environment variables but does not load Fish config
or interactive aliases/functions. Use explicit command paths when needed. It
runs with normal user privileges; do not place untrusted scripts here.

`examples/upall-custom.fish` provides an AC:Unreal example. Copy it into
the machine-local path only on machines where you want it. It:

- Skips machines without the managed `~/Games/AsheronsCall` installation.
- Skips a running `ACUnreal` process without killing anything.
- Runs the existing checksum-verified updater once for both Player and Buffbot.
- Uses no sudo and leaves client profiles, HD DATs and Steam entries in place.

The example is a direct update command with installation/process guards, not a
second installer. The AC installer handles root refusal, validation and locks.
A missing updater checkout, busy installer, race or download/hash/installation
error is a real failure, not a silent skip. The current `ac-jars` updater also
updates existing official Plugin Manager packages after v166+ binary updates.
That logic belongs to the application updater, not this Fish hook. Missing/manual
plugins and permission changes still need Plugin Manager review. The local script
does not enable optional features or start clients.

Run the custom step alone with:

```sh
fish --no-config ~/.config/upall/custom.fish
```

## Safety and scope

- Requires an existing Atelier desktop with its Hyprland and theme configuration
  linked to this checkout. This is not a replacement for `setup.sh` or the native
  login/lock activation wizard.
- Detects `mini-mecha` / `oki-mecha` using the installed profile and hostname.
  `--machine` / `HYPR_MACHINE` can identify a renamed host, but cannot silently
  replace a different installed/recognized machine profile.
- Requires clean tracked files on `main` tracking `origin/main`. Never resets,
  stashes, switches branches, force-pulls, or discards local changes. Untracked
  files are retained; untracked/ignored files inside managed Stow source packages
  block an update because they could accidentally be installed.
- Fetches only after approval, then allows only a fast-forward to `origin/main`.
  Ahead/diverged local branches stop for manual resolution. Pulling linked files
  can itself trigger application auto-reloads; the confirmation says so.
- `--check` and `--dry-run` do not fetch, install, reload, acquire an update lock,
  or write a success record. They describe **the current checkout**, not unseen
  remote changes; the displayed origin status is cached. They run read-only
  configuration validators and Stow simulation. `--check` exits unsuccessfully
  on drift or unexpected unknown checks.
- Custom `XDG_CONFIG_HOME` layouts are deliberately refused because the existing
  Stow packages target `~/.config`.

The installed scope is detected from owned links: Hyprland, Quickshell, Ghostty,
Fish, backgrounds, avatars, Zed, OpenCode, and the shared theme. Only items already
installed are refreshed. The first successful run reconciles these once. Later
runs select changes since this checkout/machine's last successful revision.
Package requirements are read from the existing `setup.sh` registry on every run;
`pacman -T` respects providers and version constraints. Missing requirements use
`paru`/`yay`, or `sudo pacman`, with normal package-manager confirmation. No full
system upgrade or orphan/removal operation is performed by `update.sh` itself.
Non-interactive mode defers missing dependencies instead of invoking a package manager.

Optional [casting](casting.md) is also tracked after `./setup.sh casting` installs
its marker. Routine updates do not add it to machines where it was never selected.

Before restowing, GNU Stow simulates the operation. Conflicting real/foreign
configuration stops the update; the updater does not adopt or replace it. The
existing application-theme/editor installers preserve unrelated settings and
back up managed settings they change. Theme updates can refresh managed appearance
preferences; they do not rerun Nautilus customization. Fish changes are restowed
without bootstrapping/updating Fisher or Tide. Changed plugin lists are reported
for manual review. External skills, Matrix, console/system installers and old
login/lock activation are not executed; changed bootstrap/policy scripts are
reported as manual follow-ups.

## Native authentication updates

The updater compares the staged root-owned login/lock UI, PAM and public assets
with the current sources even when the checkout was pulled manually. If they
differ, it lists destinations and asks **separately** before using sudo to stage
the bundle with `install_access.py --account ...`. Differing existing files are
backed up by that installer. Unknown/local PAM modifications are refused rather
than silently overwritten; a repository PAM change can be staged only when the
installed policy matches the previous successful revision.

This never selects a locker/greeter, reruns authentication enrollment, restarts
greetd, unlocks, logs out, or reboots. The existing installer refuses installation
while any native lock owns the shared bundle. If staging is declined/fails, no
success revision is recorded. Non-interactive mode defers a required refresh
without invoking sudo. Finish the update later; do not bypass the check.
After a bundle update, test password/fingerprint unlock, output coverage, resume
and a fresh login yourself. Unmigrated machines keep their existing selection.

## Validation, performance, and recovery

Generated themes and Hyprland configuration must validate. Necessary Hyprland
reloads are followed by a config-error check, and a graphical session's Quickshell
health is checked without killing/restarting it. The complete installed-scope
audit must have no drift. Only documented manual unknowns (visual appearance,
real authentication, upstream Fish plugin versions) are accepted as follow-ups;
unexpected unavailable/read-error checks stop success.

A no-source-change run skips restowing, theme/editor installation and privileged
bundle refresh when copies match. The full read-only installed-scope audit took
about **2.1 seconds on oki-mecha** during development; network fetches, missing
dependencies and actual changed-theme installation add time. No benchmark claims
are made for mini-mecha yet.

Success is recorded atomically under
`${XDG_STATE_HOME:-~/.local/state}/atelier/updates/`, keyed by machine and checkout.
An exclusive lock prevents concurrent updater runs for that checkout/machine.
Failures do not advance the revision. There is no automatic rollback: a fetch may
have advanced the checkout and earlier approved actions may have completed.
Resolve the reported issue and rerun; the old baseline keeps those changes in the
plan. Corrupt/unrelated state records stop instead of being silently replaced.

If the pull updates the updater or its imported implementation, it stops before
installation and asks you to rerun `./update.sh` in a fresh process. This avoids
applying a new checkout with an old in-memory planner.

Tests use disposable repositories/homes and fake OS commands; they do not update
the real desktop or packages:

```sh
python3 -B -m unittest discover -s tests -p test_desktop_update.py
fish --no-config fish/tests/upall.fish
python3 -B -m unittest discover -s tests -p test_custom_updater.py
```
