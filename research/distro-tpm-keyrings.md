# Distro TPM-backed keyring comparison

Date: 2026-11-22. Scope: compare Ubuntu, Fedora Workstation, Debian, openSUSE,
and KDE defaults for desktop secret storage, fingerprint/PAM unlock, and TPM2
integration. This is a source and packaging assessment, not an installation or
runtime test. No packages, credentials, services, or desktop configuration were
changed.

## Bottom line

Mainstream Linux desktop defaults still use password-based GNOME Keyring or
KWallet. TPM2 support is well established for LUKS disk unlock, systemd
credentials, and PKCS#11 tokens, but that is not the same as a TPM-backed
Secret Service vault. No checked distro source establishes TPM-backed desktop
keyring auto-unlock as the default on Ubuntu, Fedora Workstation, Debian, or
openSUSE.

The strongest current path toward passwordless keyring unlock is oo7 supplied
with a systemd credential protected by TPM2. Fedora and GNOME package/build
metadata show meaningful oo7 adoption, but the checked evidence does not prove
that Fedora Workstation has switched its default desktop configuration. The
existing oo7 assessment also found an open failed-unlock state bug in 0.7.3,
so this is not yet a low-risk migration target for the real keyring.

## Comparison

| Platform | Current evidence | TPM/keyring conclusion |
| --- | --- | --- |
| Ubuntu | Ubuntu 26.10 packages `gnome-keyring 51.1-1`; Ubuntu package search found no `oo7` package. | GNOME Keyring remains the observable packaged path. Ubuntu documents TPM for full-disk encryption, not Secret Service auto-unlock. |
| Debian | Debian Package Tracker lists `gnome-keyring 51.1-3`; no Debian `oo7` tracker package was found. | GNOME Keyring is the supported packaged path examined. No distro-level TPM keyring integration was found. |
| Fedora Workstation | Fedora packages `gnome-keyring`; Fedora 45 also packages `oo7-daemon`, `oo7-portal`, `pam_oo7`, and `oo7-cli`. | Fedora is furthest along in packaging oo7, including PAM integration, but package availability is not proof of a Workstation default or a tested TPM unlock flow. |
| openSUSE GNOME | Factory contains GNOME Keyring and also an oo7 package, while the GNOME pattern inspected did not establish oo7 as the default keyring. | Both projects are available in Factory; default desktop ownership and TPM auto-unlock were not established. |
| KDE Plasma | KWallet stores passwords; KDE documents that the default wallet is secured by the login password and auto-opens when `kwallet_pam` is installed/configured. | KWallet has PAM login integration, but no checked KDE source documents TPM-backed wallet auto-unlock as the default. |

Package presence is evidence of availability, not evidence that a particular
installer image enables the package, configures PAM, migrates existing keyrings,
or handles fingerprint-only login correctly.

## Fingerprint login and keyring unlock

GNOME documents the keyring as password-based and integrated with login. KDE
similarly documents KWallet auto-opening through the login password and
`kwallet_pam`. These are separate authentication layers from fingerprint
verification.

Therefore, fingerprint authentication alone should not be treated as proof that
a password-encrypted keyring will unlock. The decisive behavior depends on the
actual PAM stack and desktop/session integration. A working fingerprint login
can still leave GNOME Keyring or KWallet locked and cause applications to prompt
for the keyring password.

## What TPM2 can and cannot mean here

These are distinct mechanisms:

- `systemd-cryptenroll` uses TPM2 to unlock LUKS2 volumes. That protects the
  disk and does not automatically unlock a desktop Secret Service vault.
- systemd credentials can be encrypted using host or user keys, including
  TPM-backed protection. A service can then receive a credential at startup.
- `tpm2-pkcs11` exposes a TPM2 device as a PKCS#11 cryptographic token. It is
  useful for applications that consume PKCS#11, not a general GNOME Keyring or
  KWallet replacement.
- oo7 documents a systemd credential named
  `oo7.keyring-encryption-password`. In that design, systemd handles protected
  credential delivery and oo7 uses the imported value to unlock its keyring;
  oo7 does not itself implement the TPM operation.

This makes TPM-backed oo7 auto-unlock technically plausible without claiming
that ordinary GNOME Keyring or KWallet files are transparently TPM-backed.

## Practical recommendation for this machine

For the current CachyOS/Arch Hyprland setup:

1. Keep the working GNOME Keyring configuration for now.
2. Do not make the keyring unencrypted merely to avoid a prompt; that trades
   convenience for weaker at-rest protection.
3. Do not migrate the real keyring to oo7 solely because Fedora, GNOME, or Arch
   packages it. Reconsider after the failed-unlock state fix and storage work
   are in a tagged release.
4. If evaluating oo7 later, use a disposable account or copied keyrings and
   test fingerprint login, normal Secret Service clients, Flatpak portal
   clients, reboot, wrong-password retry, password change, failed decrypt, and
   loss of the TPM/systemd credential.

## Sources

### GNOME and Fedora

- [GNOME Keyring overview](https://wiki.gnome.org/Projects/GnomeKeyring)
- [GNOME Seahorse: unlock a keyring](https://help.gnome.org/users/seahorse/stable/keyring-unlock.html.en)
- [Fedora `gnome-keyring` package](https://packages.fedoraproject.org/pkgs/gnome-keyring/gnome-keyring/)
- [Fedora `oo7-daemon` package](https://packages.fedoraproject.org/pkgs/oo7/oo7-daemon/fedora-45.html)
- [Fedora `pam_oo7` package](https://packages.fedoraproject.org/pkgs/oo7/pam_oo7/fedora-45.html)

### Ubuntu, Debian, and openSUSE

- [Ubuntu `gnome-keyring` package](https://packages.ubuntu.com/stonking/gnome-keyring)
- [Ubuntu `oo7` package search](https://packages.ubuntu.com/search?keywords=oo7&searchon=names&suite=all&section=all)
- [Ubuntu TPM documentation](https://documentation.ubuntu.com/security/security-features/platform-protections/trusted-platform-module/)
- [Ubuntu full-disk encryption documentation](https://documentation.ubuntu.com/security/security-features/storage/encryption-full-disk/)
- [Debian `gnome-keyring` tracker](https://tracker.debian.org/pkg/gnome-keyring)
- [openSUSE Factory GNOME pattern](https://api.opensuse.org/public/source/openSUSE:Factory/patterns-gnome/patterns-gnome.spec)
- [openSUSE Factory GNOME Keyring spec](https://api.opensuse.org/public/source/openSUSE:Factory/gnome-keyring/gnome-keyring.spec)
- [openSUSE Factory oo7 spec](https://api.opensuse.org/public/source/openSUSE:Factory/oo7/oo7.spec)

### KDE, systemd, and TPM2

- [KDE KWallet introduction](https://docs.kde.org/stable_kf6/en/kwalletmanager/kwalletmanager/introduction.html)
- [KDE KWallet configuration](https://docs.kde.org/stable_kf6/en/kwalletmanager/kwalletmanager/kwallet-kcontrol-module.html)
- [`systemd-cryptenroll` manual](https://www.freedesktop.org/software/systemd/man/latest/systemd-cryptenroll.html)
- [systemd credentials](https://systemd.io/CREDENTIALS/)
- [`systemd-creds` manual](https://www.freedesktop.org/software/systemd/man/latest/systemd-creds.html)
- [Linux trusted and encrypted keys](https://docs.kernel.org/security/keys/trusted-encrypted.html)
- [tpm2-pkcs11 project](https://github.com/tpm2-software/tpm2-pkcs11)
- [oo7 0.7.3 server documentation](https://raw.githubusercontent.com/linux-credentials/oo7/0.7.3/server/README.md)
- [oo7 0.7.3 service unit](https://raw.githubusercontent.com/linux-credentials/oo7/0.7.3/server/data/oo7-daemon.service.in)

## Limitations

- Several distro package and source sites were protected by bot challenges;
  where possible, official package APIs or trackers were used instead.
- Fedora package metadata and GNOME build metadata demonstrate packaging and
  integration direction, not a verified Fedora Workstation installer default.
- No runtime test established fingerprint-to-keyring handoff, TPM sealing,
  login ordering, reboot behavior, or recovery behavior.
- Conclusions describe the sources visible on 2026-11-22; package and upstream
  states can change quickly.
