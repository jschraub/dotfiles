# Hyprlock on machines with and without fingerprint readers

Use the same password-only PAM stack on **both** machines. This avoids pulling
`pam_fprintd` into Hyprlock's password conversation through `auth include login`.
It does not change login, greetd, sudo, or their fingerprint policies.

The shared `scripts/lock.sh` wrapper queries fprintd for actual devices and enables
Hyprlock's **native** fingerprint backend only when a reader is reported. Missing
hardware, a missing fprintd service, or a failed device query quietly falls back
to password unlock. A password is always available. Detection does not enroll or
collect fingerprints. Super+L, Hypridle, and wlogout all use this wrapper.

Install the PAM policy from your normal account:

```sh
./install-pam-hyprlock.sh                    # auto: reader optional
./install-pam-hyprlock.sh --fingerprint off  # explicitly password-only
./install-pam-hyprlock.sh --fingerprint on   # require enrollment tools at setup
```

The policy is stored outside Stow in `~/.config/dotfiles/hyprlock-fingerprint`.
Without that file, the default is `auto`. `HYPRLOCK_FINGERPRINT=auto|on|off` overrides
it for a session. Even `on` falls back to a password if a reader is unavailable
at lock time. The wrapper uses a private temporary config under XDG_RUNTIME_DIR;
no per-machine generated configuration is written into the shared dotfiles.

On the fingerprint-capable machine, install `fprintd` and enroll through
`fprintd-enroll` interactively if it is not already configured. The sensorless
machine does not need fprintd installed. Neither setup nor audit enrolls fingers.

After restowing `hyprland-common`/`wlogout` and reloading Hyprland/Hypridle at a
convenient time, inspect the choice without locking:

```sh
~/.config/hypr/scripts/lock.sh --check
```

Keep a recovery terminal available and test `~/.config/hypr/scripts/lock.sh`
before logging out. PAM installation preserves `/etc/pam.d/hyprlock.orig` as the
original backup. A direct `hyprlock` command bypasses auto-detection and retains
the ordinary password-only default.
