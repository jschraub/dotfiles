# Atelier clipboard picker

**Super+V** opens a centered Atelier picker on the focused display. It remembers
normal clipboard text and PNG images while the desktop shell is running. The
primary selection (select text / middle-click paste) is deliberately untouched.

## Controls

- Type to search text or PNG image labels/dimensions.
- **Up/Down** select an item; **Enter** copies its original bytes and closes.
- Click an item to copy it; nothing automatically types or pastes into an app.
- **Ctrl+Delete** or an item's × removes it from history.
- **Escape**, Super+V again, or an outside click dismisses without changing the clipboard.
- **Pause history** stops new collection; remembered items remain usable.
- **Clear history** removes remembered items, not the current system clipboard.

Text is shown literally, not as HTML or executable commands. Long items have a
shortened preview, but copying restores the complete original text, including
newlines. Images get thumbnails and dimensions. Keyboard hints are green and the
layout uses spacing, not dot separators.

## Privacy and limits

- **No history database, persisted text, image files, or clipboard-content logs.**
  The helper stores history in RAM. PNG previews use sealed Linux anonymous
  `memfd` objects exposed to Qt through `/proc`, not on-disk thumbnails or data
  URLs in logs. Core dumps are disabled for capture/helper processes. Ordinary
  OS memory/swap and the system clipboard itself are not a secure secret store.
- Retains up to **50 items / 16 MiB of raw payload**, evicting the oldest entries.
  Text is limited to **256 KiB** per item. PNGs are limited to **8 MiB**, 16
  megapixels and 8192 pixels per dimension. Unsupported/binary/oversized offers
  are ignored; other image formats and rich HTML are not stored in this version.
- Source offers marked sensitive by `wl-paste` are skipped before the capture
  worker reads them. This includes `x-kde-passwordManagerHint`, used by some
  password managers. Unknown clipboard states are skipped conservatively too.
  **Not every app marks passwords/API keys.** Unmarked secrets can enter history.
  Pause before copying sensitive data, and clear history when necessary.
- Pause state is a small owner-only flag in the session runtime directory, with
  no clipboard contents. It survives helper/QML restarts so capture does not
  silently resume while paused. History itself is lost on shell/helper restart,
  QML reload or logout. An unpaused watcher may capture the current selection
  when it starts/restarts; resuming an existing watcher does not force a read.
- Deleting/clearing invalidates in-flight reads. Matching delayed clipboard echoes
  are also ignored for five seconds, so immediately copying the same removed
  value again may not add it back until that interval has passed.
- Watchers are owned by this Wayland session's helper. Linux parent-death signals
  stop capture if the shell/helper crashes. Normal shutdown removes its private
  socket directory and closes image descriptors. No clipboard data is included
  in Atelier's public shell health/status/features IPC.
- Preview and automated test shells never start real clipboard collection.
  The separate greeter, locker and polkit UI do not load this service.

## Setup and maintenance

`./setup.sh quickshell` declares `wl-clipboard` explicitly and installs the picker
with the rest of Atelier. Restow and reload Hyprland after updating an existing
checkout to install Super+V. No extra daemon/package or system service is needed.
`qs ipc -c atelier call shell features` reports clipboard capture readiness only,
never remembered content. Failed watcher processes are restarted without discarding
the live helper's history. A helper restart discards its RAM history.

Implementation: `ClipboardPanel.qml`, `ClipboardService.qml`, and `clipboard.py`.
The UI uses a dedicated private stdin/stdout protocol rather than the general
desktop backend; watcher workers use a mode-0700 directory, mode-0600 Unix socket,
same-UID peer checks, bounded payloads and epoch checks for pause/clear races.

Tests never change the real clipboard:

```sh
python -B -m unittest discover -s tests -p test_clipboard.py -v
ATELIER_GUI_TESTS=1 python -B -m unittest discover -s tests -p test_atelier_clipboard.py -v
```
