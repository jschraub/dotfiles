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

For fingerprint sign-in without a second keyring-password prompt, use the
separate [oo7/TPM keyring migration](keyring.md). Its credential is provisioned
locally on each machine and works with password-only machines too.

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
- **Fingerprint lifecycle:** a separate, root-installed monitor watches logind's
  sleep notifications and the actual kernel lid state. It disables scanning
  while the lid is closed, sleep is in progress, or the reader is unavailable.
  It requests fingerprint cancellation under a logind delay inhibitor. The
  greeter releases it after the actual greetd cancellation acknowledgement, or
  immediately when its managed password branch is already selected. No new
  greeter authentication starts during sleep preparation. A 1.5-second timeout
  releases the inhibitor if cancellation stalls or the UI stops responding;
  logind's configured inhibitor limit remains authoritative.
  Quickshell 0.3.2's locker PAM API reports `active=false` before destroying its
  worker and has no abort-completed signal. The locker therefore uses the
  bounded timeout, never a false acknowledgement based on `activeChanged`.
  This follows the upstream [PAM context implementation at 0.3.2](https://github.com/quickshell-mirror/quickshell/blob/v0.3.2/src/services/pam/qml.cpp#L96-L103).
  The monitor reprobes after a short wake-up delay. The password
  conversation and typed text stay intact across these changes. Reader discovery
  and PAM failures are retried, and fingerprint feedback is shown separately.
  A stale success after cancellation cannot unlock the session. The monitor
  requires `python-gobject`; it does not require fprintd on readerless machines.
- **Greeter:** a dedicated greetd protocol adapter; only its successful ready-to-launch
  state for the selected user launches fixed `/usr/bin/start-hyprland` argv.
  No user-entered text is interpreted as a session command.
- **Credentials:** input masked unless the provider
  explicitly requests visible input, predictive input disabled, response cleared
  before submission and on identity/prompt/result changes. Locker responses use
  native PAM. Greeter responses travel through a private parent/child stdin pipe
  directly to the inherited greetd Unix socket; the adapter never echoes them.
  There is no password-response IPC, argument, environment variable or log entry.
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

For an already-selected native locker, deploy lifecycle updates with:

```sh
./setup.sh access
sudo python3 -B scripts/install_access.py --account "$(id -un)"
```

The installer updates the bundle without locking, logging out or restarting
greetd. Test the next real lock, docked/lid-closed use, suspend/resume and the
readerless host separately. `desktop-keyring status` should remain successful
after unlocking.

### Sign-in method toggle and fingerprint restart

Enable the reader-aware toggle on an already-selected Atelier greeter:

```sh
./setup.sh access
sudo python3 -B scripts/install_access.py --account "$(id -un)" --enable-login-methods
```

This explicit step backs up `/etc/pam.d/greetd` to
`/etc/pam.d/greetd.before-atelier-methods`, and changes only its known authentication
route to the managed `atelier-login` substack. Unfamiliar local greetd PAM policies
are rejected. Account/session includes stay intact. It does not restart greetd or
log out the current desktop.

- **Reader available, lid open:** defaults to fingerprint. The amber-themed
  **Use fingerprint** toggle switches to password immediately, cancelling the
  current attempt first.
- **Scan expires or fails:** the screen stays in fingerprint mode and displays
  **Restart fingerprint**. Clicking starts a fresh attempt; it does not silently
  switch to password. A scan allows three mismatches and a 15-second timeout.
- **No reader/service:** password-only, with no fingerprint toggle. No fprintd
  package is required on the readerless host.
- **Lid closed or reader unavailable:** password-only until the reader is usable.
  A present reader's toggle stays visible but disabled while docked. Opening the
  lid does not interrupt password entry; the toggle becomes available again.

A small, locally compiled PAM module asks the greeter which branch to use. It
handles only the literal public values `fingerprint` and `password`, never a
password/auth token. It independently checks the kernel lid state. Password skips
the fingerprint module entirely; fingerprint failure ends that attempt rather
than falling through to password. Stock pam_unix/pam_systemd_home/pam_fprintd do
the authentication, and existing faillock/account/session policy stays in effect.
The module is installed root-owned under `/usr/lib/security`; no binary is stored
in Git. Setup declares gcc and PAM as build dependencies.

The greeter transport matches each server reply to its request and discards
cancelled-attempt replies. It waits for the **actual cancel acknowledgement**
before creating the replacement. An installed Quickshell 0.3.2 cancellation bug
was reproduced with the private socket test, so this path does not depend on
the native singleton's cancellation handling or a timing delay. Only a successful
authentication reply can reach ready-to-launch; a cancel acknowledgement cannot.

Once enabled, routine root-bundle refreshes rebuild the selector when updating
its sources. Audits check its root-owned checksum and the managed PAM policy.
Repeat the explicit enabling command on the other machine after syncing the repo.

Restore the previous routing from a TTY if needed:

```sh
sudo cp -a /etc/pam.d/greetd.before-atelier-methods /etc/pam.d/greetd
```

The greeter remains compatible with that original stack; its method controls
appear only after the selector handshake. No experimental concurrent PAM module
is used. The lock screen continues to offer its independent password/fingerprint
conversations; sign-in uses one selected method at a time.

Verification:

```sh
python -B -m unittest discover -s tests -p test_login_method_pam.py -v
ATELIER_GUI_TESTS=1 python -B -m unittest discover -s tests -p test_atelier_access.py -v
ATELIER_GUI_TESTS=1 python -B -m unittest discover -s tests -p test_greetd_methods_protocol.py -v
```

The first test uses actual libpam with a private PAM configuration and stock
permit/deny substitutes, including a missing fingerprint module. The others use
fake providers and a private socket; they never submit real credentials or launch
a real session. Hardware verification still requires a fresh sign-in, scan
expiry/restart, password switching, lid-closed docking and the readerless machine.
