# oo7 keyring maturity assessment

Date: 2026-11-22. Scope: assess `linux-credentials/oo7` 0.7.3 as a possible
GNOME Keyring replacement on CachyOS/Arch, including systemd credential and TPM2
auto-unlock. This is a source and packaging assessment, not an installation,
migration, or runtime acceptance test. No packages, credentials, services, or
desktop configuration were changed.

## Bottom line

Do **not** replace the working GNOME Keyring setup with oo7 yet if the priority
is proven reliability and future support. oo7 0.7.3 is a credible, actively
maintained, Arch-packaged candidate with the required Secret Service, PAM,
portal, migration, and systemd credential pieces. However, the available 0.7.3
release was published only yesterday, the
current development line is already 0.8.0-alpha, and upstream still has an open
unlock-state correctness bug plus an open V1 storage refactor. That is not enough
evidence for a risk-sensitive credential-store migration.

The right conclusion is **promising but not mature enough for immediate cutover**,
not “unsafe” or “unsupported.” Reconsider after the open storage work and failed-
unlock fixes have landed in a tagged release, and after a disposable-profile
acceptance test covers login, reboot, migration, Secret Service clients, portal
clients, and failure recovery.

## What was verified

### Release and packaging

- GitHub lists [0.7.3](https://github.com/linux-credentials/oo7/releases/tag/0.7.3)
  as a published, non-draft, non-prerelease release created and published on
  2026-11-21.
- The tag ref resolves to commit
  [5cbd7a6](https://github.com/linux-credentials/oo7/commit/5cbd7a60afd8bd73063b98e553d908205cdc14a2),
  an unsigned version-bump commit. The release metadata names `main` as its
  target branch, while the actual tag ref resolves to the version-bump commit;
  the earlier [#710 report](https://github.com/linux-credentials/oo7/issues/710)
   documented confusion around this and was closed. These metadata differences
   do not establish that the resolved tag is an alpha build.
- Current `main` is 0.8.0-alpha in `Cargo.toml`. Stable 0.7.3 and current
   development should not be treated as the same support target.
- The [repository metadata](https://api.github.com/repos/linux-credentials/oo7)
  dates repository creation to 2022-04-22. The project itself is not a day old;
  that date describes the latest release, not the age or deployment history of
  the daemon and TPM integration.
- Local package metadata reports CachyOS `oo7 0.7.3-1.1` and Arch `oo7 0.7.3-1`,
  both built on 2026-11-21. The Arch package includes `oo7-daemon`, PAM, portal,
  CLI/tools, and Python bindings, and provides `org.freedesktop.secrets`.
- Arch still lists [gnome-keyring](https://archlinux.org/packages/extra/x86_64/gnome-keyring/)
  as a separate package. oo7 being packaged in Arch does not mean Arch has made
  it the default replacement.
- The [Arch security tracker](https://security.archlinux.org/package/oo7) showed
  no listed issues. That is useful packaging evidence, but it is not evidence of
  an independent security audit.

### Systemd credentials and TPM2

The tagged [server README](https://raw.githubusercontent.com/linux-credentials/oo7/0.7.3/server/README.md)
documents a systemd credential named `oo7.keyring-encryption-password`, requires
systemd 258 or newer, and shows encrypted user-credential setup. The tagged
[service unit](https://raw.githubusercontent.com/linux-credentials/oo7/0.7.3/server/data/oo7-daemon.service.in)
uses `ImportCredential=oo7.keyring-encryption-password`.

This is a sound division of responsibility:

- `systemd-creds`/systemd handles credential encryption and can use TPM2-backed
  host/user keys according to the [systemd CREDENTIALS documentation](https://systemd.io/CREDENTIALS/)
  and [`systemd-creds` manual](https://www.freedesktop.org/software/systemd/man/latest/systemd-creds.html).
- oo7 receives the imported credential and uses it to unlock its keyring. oo7
  does not itself implement TPM operations.
- The user's systemd 262 meets oo7's documented minimum. TPM2 availability makes
  the design plausible, but this review did not test boot, login, credential
  import, lock/unlock, or recovery behavior.

Therefore TPM-backed auto-unlock is a supported integration path in principle,
not a verified property of this machine.

### Storage and compatibility

The tagged [server README](https://raw.githubusercontent.com/linux-credentials/oo7/0.7.3/server/README.md)
documents V1 storage under `$XDG_DATA_HOME/keyrings/v1/`, a libsecret-compatible
file format, and migration from old GNOME Keyring files. It identifies PBKDF2-
HMAC-SHA256, AES-128-CBC, and HMAC-SHA256 for the V1 format.

The tagged [client README](https://raw.githubusercontent.com/linux-credentials/oo7/0.7.3/client/README.md)
documents the Secret Service DBus and encrypted-file backends. The tagged
[client manifest](https://raw.githubusercontent.com/linux-credentials/oo7/0.7.3/client/Cargo.toml)
also exposes an `unstable` API feature, which is relevant to applications that
use oo7 as a library rather than only through the daemon protocol.

The documented migration path is encouraging, but credential-store migration is
not merely a file-copy operation. It changes the daemon, unlock paths, password
changes, and recovery behavior. That is why migration correctness matters more
than the existence of a parser or a compatible file format.

## Reliability evidence

The 0.7.3 release notes include meaningful fixes: pending migration handling,
retrying wrong CLI secrets, preventing deletion of migration placeholders,
keeping a keyring after failed unlock, deterministic collection ordering, and an
OpenSSL padding fix. The tagged source contains the padding fix in commit
[ccc5fb9](https://github.com/linux-credentials/oo7/commit/ccc5fb916ec3698aa22bcd3557b0d1798b8b5add).

That fix addressed a real intermittent interoperability failure: an OpenSSL DH
shared secret with a leading zero could produce a different HKDF input, causing
libsecret lookups/stores and unlock prompts to fail intermittently. It is a good
sign that upstream investigated and fixed a subtle cryptographic
interoperability bug before this release. It is also evidence that 0.7.3 is
close to active bug-fix work, not a long-settled implementation.

The following upstream items are more important for a migration decision:

| Item | State at assessment | Significance |
| --- | --- | --- |
| [#650](https://github.com/linux-credentials/oo7/issues/650) empty systemd credential cannot unlock an unencrypted keyring | Closed | Demonstrates that empty-password and systemd-startup semantics required explicit fixes. The release notes claim related handling, but this is a migration edge case worth testing. |
| [#696](https://github.com/linux-credentials/oo7/issues/696) password change during pending V0 migration fails after reboot | Closed | Shows that migration and password-change paths have recently had data-integrity consequences. 0.7.3 release notes claim the relevant fix. |
| [#707](https://github.com/linux-credentials/oo7/issues/707) libsecret intermittently cannot find secrets | Closed | Real OpenSSL interoperability bug; fixed in the tagged source, but discovered immediately before 0.7.3. |
| [#712](https://github.com/linux-credentials/oo7/issues/712) Secret portal from 0.7.3 fails with missing `token` | Closed | Indicates 0.7.3 initially had a Flatpak portal integration regression. Closure is not a substitute for verifying the fix in the packaged build. |
| [#711](https://github.com/linux-credentials/oo7/pull/711) V1 storage adapter | Open | Broad internal storage work is under review. A refactor alone does not imply a file-format change or defect in the released version, but its discovered regressions warrant attention. |
| [#713](https://github.com/linux-credentials/oo7/issues/713) failed collection unlock can leave some items unlocked | Open | A failed unlock can report the collection locked while an earlier item reports unlocked. This violates an important atomicity/security invariant. |
| [#714](https://github.com/linux-credentials/oo7/pull/714) preserve collection/item state on failed unlock | Open draft | Proposed fix for #713; not merged and therefore not part of 0.7.3. The PR reports 161 daemon tests passing, but that is contributor test evidence, not a released fix. |

The open #713/#714 pair is the strongest reason not to migrate now. A keyring
must fail closed and leave observable state coherent when an unlock or decrypt
operation fails. A fix being actively reviewed is positive for maintenance, but
it does not establish that the released package has the corrected behavior.

## GNOME adoption and support

Official GNOME build metadata was inspected from the current
[`gnome-build-meta`](https://gitlab.gnome.org/GNOME/gnome-build-meta) checkout.
It contains `oo7-daemon`, `oo7-pam`, `oo7-portal`, and an oo7 CLI element. The
daemon element installs and enables the user service through `gnome-session.target`.
The shared [oo7 metadata](https://gitlab.gnome.org/GNOME/gnome-build-meta/-/blob/master/elements/core-deps/oo7.inc)
currently tracks `v0.6.0-alpha-378-g7fb0fd5d807e4afdc8cebee7555071ea5d39c260`;
its comments distinguish nightly tracking of `main` from stable channels and
say stable should exclude alpha/beta/rc versions until bugs are resolved.

No `gnome-keyring` files were present in the current cloned build-meta tree.
This is evidence of meaningful GNOME OS/build integration and an intended
replacement direction. It is not evidence that all GNOME desktop distributions,
Arch, or third-party applications have completed a default migration. No broad
official GNOME adoption announcement or independent audit disclosure was found
in the checked first-party sources.

## Security assessment

Positive evidence:

- The design can keep the encrypted credential outside oo7 and let systemd own
  TPM-backed credential protection.
- V1 uses authenticated encryption components as documented: AES-CBC plus
  HMAC, with PBKDF2 for password-derived keys.
- The project responds to security-relevant correctness reports, including the
  tagged OpenSSL padding fix and malformed/short encrypted-content handling in
  the 0.7.3 release notes.
- The Arch security tracker had no listed oo7 issues at the time checked.

Limitations:

- No first-party independent security audit or formal audit report was located
  in the checked upstream security page and repository sources. This means
  “audit not located,” not “no audit exists.”
- The release tag and commits checked are unsigned according to GitHub's commit
  verification metadata.
- The open failed-unlock state bug is a security-relevant correctness concern,
  even though it does not by itself demonstrate plaintext leakage.
- No runtime test established TPM sealing, credential permissions, login ordering,
  reboot behavior, or behavior when TPM/systemd credential import fails.

## Recommendation

For this machine and the stated reliability preference:

1. Keep the existing GNOME Keyring setup for now. Do not migrate the real keyring
   or enable oo7 as the production owner based on package availability alone.
2. Watch for a tagged release that includes merged equivalents of #713/#714 and
   settles the #711 storage adapter work. Recheck the release notes and exact tag
   contents rather than assuming fixes on `main` are packaged.
3. If evaluating later, use a disposable account or copied test keyrings first.
   Cover PAM login unlock, normal Secret Service clients, Flatpak portal clients,
   V0 migration, password change, reboot, wrong-password retry, failed item
   decrypt, and loss of TPM/systemd credentials.
4. Treat TPM2 auto-unlock as an integration acceptance criterion: verify that the
   secret is sealed/imported by systemd, that oo7 starts after the credential is
   available, and that failure leaves the keyring locked without destructive
   migration or partial item state.

## Scope and limitations

- Research was read-only with respect to the local desktop and credentials.
- No package installation, service enablement, migration, unlock, reboot, or
  runtime Secret Service test was performed.
- Arch package metadata was available, but direct PKGBUILD pages were blocked by
  the package site's bot protection. GNOME GitLab web/API pages were also partly
  blocked; the official build metadata repository was cloned locally for the
  deployment inspection.
- Conclusions are based on the state visible on 2026-11-22. Upstream issue and
  package states can change quickly.

## Primary sources

- [oo7 repository](https://github.com/linux-credentials/oo7)
- [oo7 0.7.3 release](https://github.com/linux-credentials/oo7/releases/tag/0.7.3)
- [0.7.3 tag](https://github.com/linux-credentials/oo7/tree/0.7.3)
- [0.7.3 server README](https://raw.githubusercontent.com/linux-credentials/oo7/0.7.3/server/README.md)
- [0.7.3 service unit](https://raw.githubusercontent.com/linux-credentials/oo7/0.7.3/server/data/oo7-daemon.service.in)
- [0.7.3 client README](https://raw.githubusercontent.com/linux-credentials/oo7/0.7.3/client/README.md)
- [systemd CREDENTIALS](https://systemd.io/CREDENTIALS/)
- [`systemd-creds` manual](https://www.freedesktop.org/software/systemd/man/latest/systemd-creds.html)
- [Arch oo7 package](https://archlinux.org/packages/extra/x86_64/oo7/)
- [Arch oo7 file list](https://archlinux.org/packages/extra/x86_64/oo7/files/)
- [Arch oo7 security tracker](https://security.archlinux.org/package/oo7)
- [GNOME build metadata](https://gitlab.gnome.org/GNOME/gnome-build-meta)
- [GNOME oo7 build metadata](https://gitlab.gnome.org/GNOME/gnome-build-meta/-/blob/master/elements/core-deps/oo7.inc)
