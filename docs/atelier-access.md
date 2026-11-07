# Atelier login and lock screens

These are separate Quickshell entrypoints, not part of the desktop bar process.
The design preserves the existing Balrog background and Gandalf avatar, with
Atelier graphite surfaces, Inter typography, amber accents and light-gray text.
A clock/date sits at the upper right; the centered form has a circular avatar.
Login is headed “Speak, friend, and enter.”; locking uses “Keep it secret. Keep it
safe.” Authentication prompts and failure messages remain literal and clear.

## Preview, install, test, select

Run as your normal user inside Hyprland:

```sh
./setup.sh access
./scripts/setup-atelier-access.sh
```

The four-stage wizard:

1. Opens a **visual-only** preview. It cannot authenticate or lock.
2. Uses sudo to stage root-owned UI, public assets and two separate PAM services.
   Existing greetd/login/sudo policies and live lock selection remain unchanged.
3. Asks before a **real password lock/unlock test**, with fingerprint disabled for
   that test. If a reader is detected, a separate real fingerprint test follows.
4. Selects the native locker and the new greetd UI only after successful testing
   and human confirmation. It never restarts greetd, logs out, reboots, or removes
   Hyprlock/ReGreet automatically. The next login tests the new greeter for real.

Sudo collects its own password. The wizard never captures a password, fingerprint,
or authentication response. Don't change the installed UI while a lock is active;
the installer serializes against the native wrapper's lock to prevent this.

For just the preview:

```sh
qs -p ~/.config/quickshell/atelier/access-preview.qml
ATELIER_ACCESS_PREVIEW=greeter qs -p ~/.config/quickshell/atelier/access-preview.qml
```

Close the preview process with Ctrl+C in its terminal. Preview uses your existing
home assets; installed authentication uses system-readable copies, never access
to a private home from the greeter account.

## User avatars

The metadata helper uses the real UID for lock identity (not `$USER`) and lists
regular local interactive accounts for login. A user's conventional
`/var/lib/AccountsService/icons/<username>` icon takes priority. Otherwise it uses
`/usr/share/atelier/access/avatars/<uid>.png`; the installer associates the existing
avatar with the account named by `--account`. Accounts without an icon display
their initial rather than another user's avatar. Names are display text, not
commands; passwords are never passed through the metadata helper.

To stage the preserved avatar for another local account, an administrator can run:

```sh
sudo python3 -B scripts/install_access.py --account USERNAME
```

The greeter never needs permission to read that user's home. No AccountsService
daemon or fingerprint reader is required for password-only use.

## Security boundaries

API references: [Wayland session lock](https://quickshell.org/docs/v0.3.0/types/Quickshell.Wayland/WlSessionLock/),
[PAM](https://quickshell.org/docs/v0.3.0/types/Quickshell.Services.Pam/PamContext/),
[greetd](https://quickshell.org/docs/v0.3.0/types/Quickshell.Services.Greetd/Greetd/).

- **Locker:** `WlSessionLock` / `ext-session-lock-v1` creates a real lock surface on
  every output, including outputs created while locked. Authentication starts
  only after the compositor reports secure coverage. Only PAM success unlocks;
  no button, Escape shortcut, timer, IPC method or process failure can do so.
- **Failure:** a crashed locker leaves the compositor locked, possibly showing
  only a solid color. This is fail-closed, not an automatic recovery/unlock.
- **PAM:** `atelier-lock` preserves the existing password-only pam_unix/faillock
  stack. Fingerprint uses a separate `atelier-fingerprint` context containing
  pam_fprintd, never the password conversation. The existing auto/on/off policy
  in `~/.config/dotfiles/hyprlock-fingerprint` remains effective; absent hardware
  means password-only. Enrollment and login/sudo fingerprint policy are unchanged.
- **Greeter:** native greetd conversation; only its successful ready-to-launch
  state for the selected user launches fixed `/usr/bin/start-hyprland` argv.
  No user-entered text is interpreted as a session command.
- **Credentials:** direct native conversation, input masked unless the provider
  explicitly requests visible input, predictive input disabled, response cleared
  before submission and on identity/prompt/result changes. No credential backend,
  stdin protocol, command-line argument, log statement or response IPC exists.
- **Files:** `/etc/atelier/access` and its parents are root-owned; runtime account
  metadata does not control code. Root-owned static files live outside Stow.
  The greeter compositor retains the existing GPU, HDR/SDR, refresh and lid rules;
  only its UI launch command changes. Root config activation preserves VT/user
  and unrelated settings and rejects an unrecognized local launch command.

## Recovery

Keep a TTY login available during the first test. If native locking fails closed:

1. Switch with Ctrl+Alt+F2 and log in normally.
2. Use `loginctl list-sessions` to identify the **graphical** session.
3. `loginctl terminate-session ID` ends that session; it does not unlock/expose it.
4. Remove `~/.config/dotfiles/lock-screen` to select the existing Hyprlock wrapper.

For a failed greeter, from a TTY:

```sh
sudo cp -a /etc/greetd/config.toml.before-atelier /etc/greetd/config.toml
sudo systemctl restart greetd
```

Restarting greetd is a recovery action and can end a graphical session. The wizard
never runs it. Keep the old packages until actual password/failure/retry,
fingerprint (if used), multi-output/hotplug, suspend/resume, and fresh login/logout
have passed on **each** machine. Fake tests are not a substitute for those checks.

## Maintenance and tests

After real login/lock validation on a particular machine, retire only its old UI
packages with `sudo pacman -R hyprlock greetd-regreet`. Keep greetd, Quickshell,
Hypridle and PAM installed. Setup/audit no longer require Hyprlock when the native
lock selector is set, and the selected native greeter is not reverted by setup.
Do not remove those packages on an untested machine. If you later need the legacy
recovery paths above, reinstall their respective packages before selecting them.

```sh
./check-setup.sh access
python -B -m unittest discover -s tests -p test_access_install.py
ATELIER_GUI_TESTS=1 python -B -m unittest discover -s tests -p test_atelier_access.py
```

Tests use fake PAM/greetd objects and compile (but do not instantiate) the real
entrypoints. They do not lock the live session or exercise real credentials.
Restage root-owned UI after changing shared styles with the installer above;
once selected, `setup.sh greetd` updates the native UI without restoring ReGreet.
