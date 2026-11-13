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
- **Expiry** cycles **Off → 5 min → 30 min → 1 hour → Off**. Off is the default.
  The control is keyboard-accessible with Tab/Enter; its description explains the cycle.

Text is shown literally, not as HTML or executable commands. Row labels explicitly
show an ellipsis when their 240-character summary is shortened. A long text preview
reports exactly how many of its Unicode characters are shown (up to 16,384) and
retained. Copying restores the complete original bytes, including newlines and
characters beyond the preview. Selected images have a larger aspect-preserving
preview, dimensions and a PNG/original-copy label in addition to their list thumbnail.
Selected previews request at most 1024×768 pixels; history still retains the original PNG.
New arrivals retain the selected item by ID rather than jumping the inspected
preview to the newest entry. Keyboard hints are green and the layout uses spacing,
not dot separators. Controls wrap on narrow layouts; the panel can scroll on a
small logical viewport.

## Optional automatic expiry

Expiry is measured from the most recent **external capture** of each item. A
duplicate external capture refreshes that timestamp; copying a remembered item
from the picker does not extend it. Reducing the limit immediately removes items
already older than that limit. Turning expiry off retains remaining items but
does not restore anything already removed.

The helper checks for expiry on reads/copy/ingest and in its background monitor
approximately every two seconds, even when the picker is closed or capture is
paused. Expiring an image closes its sealed anonymous-memory descriptor. Expiry
invalidates in-flight captures just like delete/clear. It uses Linux boot elapsed
time, including suspend, rather than adjustable wall-clock time; after resume,
old entries disappear on the next check. The timer is not a secure memory-erasure
guarantee, and scheduling may delay an idle background check.

**Expiry does not clear the current system clipboard, change saved screenshots,
or paste anything.** An unpaused helper restart can capture the current system
selection again, including a previously expired value; that fresh capture starts
a new lifetime. Pause before handling secrets. Source hints are still the only
automatic sensitive-content exclusion; unmarked secrets can be remembered.

Only the chosen expiry interval is saved, as owner-only content-free metadata in
the session runtime directory. It survives helper/QML restarts, like pause state;
there is still no on-disk history. A new runtime starts with expiry off. An invalid
saved interval fails helper startup rather than silently disabling expiry.

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
- Pause state and the optional expiry interval are small owner-only metadata in
  the session runtime directory, with no clipboard contents. They survive helper/QML restarts so capture does not
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
