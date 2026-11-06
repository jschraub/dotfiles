# Checking setup drift

Run as your normal user, not with sudo:

```sh
./check-setup.sh                       # default expectations; optional Matrix excluded
./check-setup.sh hyprland fish waybar tty greetd pam upall
./check-setup.sh --verbose tty greetd  # include successful checks
./check-setup.sh --machine mini-mecha hyprland
./check-setup.sh --list
```

The script is read-only: no installations, repairs, network requests, authentication
prompts, credential lookups, service restarts, or sleep/lock actions. It does not
print file contents or secrets. It requires Python 3 and Bash; package checks use
Arch's `pacman`. Missing query tools or inaccessible files are reported explicitly.

## What is intended?

The baseline is **this checkout's current files**, not a snapshot of the machine's
first install. Uncommitted edits are part of that baseline. Stowed files point into
the checkout, so editing one already changes the installed file: that is not drift
between disk and the checkout. Use `git diff` to see changes from the last commit.

Package names, optional-item flags, and Stow packages come from the `setup.sh` registry. The machine's
Hyprland profile is inferred from its hostname or selected with `--machine` /
`HYPR_MACHINE`. The setup menu does not record past selections: the default audit
checks default items, so absent gaming/apps may be reported as drift. Matrix hardware
is explicitly optional and excluded from both `setup.sh all` and default audits;
request `matrix` by name only on machines that use it. Pass
the same item names you selected during setup to restrict it. `pam` and `upall`
add checks for the separate system installers.

## Coverage

- Declared packages must be installed; exact package versions are not pinned.
  Waybar is an exception: stable >=0.16.0 is required for Lua workspace clicks;
  `waybar-git` is an accepted fallback. `./setup-waybar.sh` migrates a Git install
  to stable once a sufficiently new stable package is available in the local
  sync database. `--stable` refuses to fall back, without removing the current bar.
- Each file in selected Stow packages must resolve to this checkout with matching
  contents. An identical independent copy is still drift (it will not track edits).
  Extra local files and generated state are deliberately ignored.
- Greetd/ReGreet configs, greeter PAM and assets are compared with installer sources;
  the greeter Lua launch command is covered by the full config comparison. Greetd's
  persistent service enablement and key config permissions are checked. Static
  configs and `/etc/greetd` must be root:root; only ReGreet state/log directories
  are greeter-owned. A root-owned file inside a greeter-writable directory is
  not sufficient protection, so the directory itself is checked too.
- TTY font and Fish source hook, Hyprlock PAM, installed upall gate and generated
  sudoers policy are checked. The root-only sudoers policy will normally be UNKNOWN
  without elevated access; the audit never attempts sudo itself.
- Nautilus settings are queried with `gsettings get`, never `set`.
- Fisher/Tide presence and external Matrix/skills checkout layout are checked.
  Moving upstream versions, delegated Matrix installation, plugin runtime behavior,
  credentials, and firmware are **not** fully verifiable from this repo and are
  explicitly UNKNOWN. The script does not fetch upstream repositories.

This is an installation/configuration audit, not a hardware or security scan, and
does not prove that live processes have reloaded files or that suspend/resume works.
When changing an installer's system-file mappings or generated settings, update the
corresponding checks in `scripts/check_setup.py` and its tests too.

## Results

- `OK`: checked expectation matches.
- `DRIFT`: missing or different configuration, package, link, or checked metadata.
- `UNKNOWN`: not verifiable with current access/tools or not pinned by the installer.

Exit code **0** means all selected checks match, **1** means drift exists, and **2**
means no drift was found but some checks are incomplete (also used for CLI errors).
Review each difference before choosing an installer; intentional customizations are
not necessarily mistakes. In particular, never automatically overwrite PAM or
sudoers settings based only on an audit result.
