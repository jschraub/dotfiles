# Keep-awake / suspend investigation — 2026-10-17

## Original observations on the affected laptop

All times below are local (CDT), from the captured October 17 boot. These are
historical observations, not the machine's current boot or configuration.

- 02:14:53: logind accepted suspend from `systemctl` in the user's session;
  the kernel entered deep/S3 suspend. This is consistent
  with Hypridle's 1800-second listener, but the journal does not identify
  the requesting process's parent, so attribution to Hypridle is not proven.
- 10:04:24–25: the kernel and systemd completed resume. Three xHCI controllers
  logged `xHC error in resume, USBSTS 0x401, Reinit`. USB hub/device recovery
  then logged timeouts (`-110`) and protocol errors (`-71`). These could leave
  USB input unavailable and make a resumed machine appear stuck.
- 10:04:57: a short power-key press initiated an orderly shutdown.
- 10:09:16: the current boot began.

The active Waybar directory and Hypridle/shared/machine-specific Hyprland
configs resolve into this repository through Stow links. `hyprland.lua` is
the active entrypoint; the absence of `hyprland.conf` is intentional.

Hypridle has `ignore_wayland_inhibit = false` and no listener override.
Waybar's toggle has no expiration configured. logind's effective IdleAction
is the default `ignore`, so its own idle timer is not an explanation.
The absence of a Waybar entry in `systemd-inhibit --list` is expected:
Waybar uses the Wayland idle-inhibit protocol, not a logind inhibitor.

## Not established

Why the inhibitor did not prevent suspend. Both Waybar and Hypridle had
stdout attached to `/dev/null`, Hyprland debug logs were disabled, and the
previous runtime directory did not survive shutdown. There is no recorded
toggle state or process/reload history sufficient to establish the cause.

Ranked avenues: a lost/reset inhibitor following bar/output lifecycle changes;
a compositor/inhibitor interaction; or another session process requesting
suspend. None is confirmed. A full suspend/wake reproduction was deliberately
not attempted during the live session.

## Logging-only changes

- Launch Waybar through `systemd-cat`, retaining its normal log level.
- Initially launch Hypridle through `systemd-cat --verbose` to record listener
  actions, inhibit changes, locking, and sleep/resume handling. Following the
  investigation below, new logins use normal logging to reduce noise.
- Log keep-awake clicks as **intent**, not a claim about its current state.
- Log the display/lid script's requests to reload Waybar.

These do not change idle timeouts or replace the inhibitor. The launch changes
take effect on the next login; merely reloading Hyprland does not rerun the
`hyprland.start` hook. Restarting Waybar manually resets its toggle: turn
keep-awake on again afterward. The journal is already persistent on this host
(`/var/log/journal` exists and previous boots are available). Check persistence
separately on other machines sharing these dotfiles.

## Capture the next occurrence

After logging out/in, verify the journal receives startup messages:

```sh
journalctl -b -t waybar -t hypridle -t dotfiles-power --no-pager
```

Turn keep-awake on and note the time and icon state. If it changes, or the bar
disappears/reappears, note that too. After an unexpected suspend, inspect the
same boot's combined sequence (use `-b -1` if rebooted):

```sh
journalctl -b -o short-precise -t waybar -t hypridle -t dotfiles-power -t systemd-logind --no-pager
journalctl -b -k --no-pager -g 'PM:|ACPI: PM:|xhci|usb|amdgpu|drm'
```

Journals may contain personal information; redact before sharing.

## Fix decisions once evidence is available

- If Waybar/output lifecycle drops keep-awake, move the toggle's ownership to
  a session-scoped logind **idle** inhibitor independent of the bar, with its
  displayed state read from that owner. Hypridle honors systemd idle inhibitors.
  An idle-only inhibitor preserves explicit/manual suspend; a sleep blocker
  would change that policy and should not be added silently.
- If Hypridle fires despite a demonstrably active Wayland inhibitor, reproduce
  with a harmless short-timeout listener before changing/updating the compositor
  or idle daemon. Do not use real `systemctl suspend` as the test action.
- Investigate the USB resume issue separately with a supervised suspend test,
  direct-connected keyboard versus the hub, and supported BIOS/firmware/kernel
  updates. Do not change sleep modes or USB power settings without a comparison
  test. The current logs establish errors, not a verified hardware fix.

## Follow-up and corrections — 2026-10-19

The retained logs show HDMI-A-1 disappearing at 2026-10-18 13:14:08, a temporary
FALLBACK output, and two display-script Waybar reloads. Hypridle then dimmed at
13:16:40, locked at 13:19:10, powered the display off at 13:19:40, and explicitly
ran `systemctl suspend` at 13:44:10: exactly 30 minutes after the last reload.
This strongly implicates the display/bar lifecycle but does not directly prove
the old Wayland inhibitor's state. The original click logs have rotated away.

Resume completed at 2026-10-19 09:29:20–21 with the same three xHCI errors.
Local input restored the display at 09:52:50; authentication succeeded at
09:53:01. Therefore this attempt did not reproduce a failed display/input wake.

Implemented:

- Replace `idle_inhibitor` with `custom/keep-awake`. The Stow-managed
  `waybar/.local/bin/keep-awake.sh` starts a transient user service holding a
  logind **idle-only** inhibitor. It survives Waybar/output recreation and exits
  within about two seconds of its originating Hyprland process ending. PID
  starttime checking prevents attaching its lifetime to a reused PID. An
  ambiguous multiple-Hyprland session is rejected instead of guessed.
- Read the actual logind inhibitor state for the icon; log acquisition/release.
  The service is not enabled at login: keep-awake starts off in a new session.
  Troubleshoot using `journalctl --user -u dotfiles-keep-awake.service` and
  `journalctl -t dotfiles-power`. Toggle manually using
  `~/.local/bin/keep-awake.sh toggle`.
- Explicitly honor systemd inhibitors in Hypridle. The existing live process
  already honors them and logged `systemd idle inhibit active` / `Inhibit locks:
  1`; it was not restarted. Verbose logging ends on the next login.
- Enable `misc.key_press_enables_dpms` in shared Lua and in the current session.
- Remove unsupported Hyprlock `general:disable_loading_bar` and
  `input-field:fail_timeout`. Do not migrate the old zero to the modern general
  authentication-failure timeout: that would change authentication policy.
- Add missing CSS `px` units.
- Stop, disable, and delete the explicitly retired local user unit
  `~/.config/systemd/user/signal-ron-weasley.service`. It was a real local file,
  not a Stow link; unrelated Signal configuration/account data was not deleted.

Validation: live integration tests (`DOTFILES_LIVE_TESTS=1 PYTHONDONTWRITEBYTECODE=1
python -m unittest discover -s tests -p test_keep_awake.py -v`) verify that an actual logind inhibitor survives its
launcher and releases on session-process exit, and that status matches logind.
An actual Waybar reload retained the same keep-awake service PID and active
inhibitor. Lua/shell syntax, JSONC parsing, diff whitespace checks, and Stow
simulation passed. No suspend or desktop restart was performed. Keep-awake was
left **on** for the current session; explicit/manual suspend remains allowed.

Still outstanding: this host's vendor journald drop-in caps storage at 50 MB.
Increasing it needs an administrator-owned override under
`/etc/systemd/journald.conf.d/`, not a Stow link or an edit to `/usr/lib`.
Passwordless sudo was unavailable, so system retention and firmware/kernel/USB
settings were not changed. Stopping the obsolete crash loop and reducing
future trace logging should substantially reduce journal churn.

## Pre-commit review — 2026-11-06

- Live tests are now opt-in (`DOTFILES_LIVE_TESTS=1`); ordinary test discovery
  does not start user services or acquire real inhibitors. Mocked status tests
  cover own-user filtering, idle-only blocking, query failures, and malformed
  logind output. Invalid responses display an error rather than claiming off.
- The live test exercises the real holder lifecycle with a disposable session
  process, not a real Hyprland logout or Waybar reload. The reload observation
  above is historical/manual evidence, not automated regression coverage.
- No full suspend/resume test is implied; the USB resume issue is still separate.
