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
```
