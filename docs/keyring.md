# oo7 keyring with machine-local TPM unlock

oo7 replaces GNOME Keyring's **Secret Service** role. systemd supplies its
decryption password from an encrypted, user-scoped credential protected by both
the host key and TPM2. Fingerprint or password authentication admits the user to
the desktop; the TPM-backed credential unlocks the keyring independently.

The same setup works without a fingerprint reader. A closed lid changes the
authentication method, not keyring availability. Neither fingerprints nor
passwords are stored in this repository. TPM-protected credentials must be
provisioned separately on **each computer and each account**.

## Install and migrate

Run inside your graphical session, as your normal account:

```sh
./scripts/setup-oo7.sh
```

The four-stage wizard:

1. Installs `oo7>=0.7.3`, systemd >=258, the shared tooling and retained GNOME
   PKCS#11 dependency through `setup.sh keyring`. It checks this computer's TPM2.
2. Asks privately for the **current login keyring password**. A copied keyring is
   opened by oo7 on a private D-Bus session with isolated data/config/runtime
   directories. The real provider is not touched during this test. Only a
   password that unlocks the copied default collection is sealed.
3. Backs up the original keyrings and provider settings, switches Secret Service
   to oo7, restarts GNOME's daemon with **PKCS#11 only**, and starts oo7. If the
   default collection does not unlock, it restores the prior provider settings.
4. Verifies that oo7 owns Secret Service and its default collection is unlocked.
   This check reads lock state, not stored secrets.

The one-time password prompt is necessary to provision encryption. Subsequent
fresh sign-ins do not need a typed password to decrypt the default keyring when
the TPM credential loads successfully. No `pam_oo7` login-password handoff is
needed for this mode; it uses the same credential for password and fingerprint
sign-in. Desktop locking does not deliberately relock the keyring.

This does **not** change the fingerprint reader driver or greetd's sequential
PAM conversation. The [sign-in method toggle](atelier-access.md) offers explicit
fingerprint/password selection and fingerprint restart instead of concurrency.
The [native lock's reader/lid/sleep lifecycle](atelier-access.md) has separate
deployment steps and requires hardware testing; switching keyrings alone does
not repair fingerprint authentication.

## Locations and synchronization

| Data | Location | Sync through Git? |
| --- | --- | --- |
| Tooling and provider templates | `keyring/` in this repo | Yes |
| Provider selection | `$XDG_CONFIG_HOME/dotfiles/keyring` | No; created after successful migration |
| TPM credential | `$XDG_CONFIG_HOME/credstore.encrypted/oo7.keyring-encryption-password` | No |
| oo7 encrypted keyrings | `$XDG_DATA_HOME/keyrings/v1/` | No |
| Original keyrings and provider backup | `$XDG_STATE_HOME/atelier/keyring/backup-*` | No |
| Migration/rollback record | `$XDG_STATE_HOME/atelier/keyring/migration.json` | No |

XDG defaults are `~/.config`, `~/.local/share` and `~/.local/state`. The backup
and credential directories are private; files are mode 600. The provisioning
helper requires `host+tpm2` encryption, scoped to the account and sealed to
**PCR 7**. It never silently falls back to host-only encryption.

PCR 7 follows the current boot-policy measurement. TPM reset, motherboard/host
key replacement or relevant Secure Boot policy changes can require provisioning
again. Keep the original keyring password independently of this computer.
TPM-backed automatic unlock is not cryptographically gated by a fingerprint:
root on the running host can obtain the secret. See the [systemd credential
model](https://systemd.io/CREDENTIALS/).

`./update.sh` detects installed keyring tooling and keeps it in sync. For an
already-selected oo7 provider, it refreshes the generated settings only when
they still match the last installed copies, then reloads unit definitions. It
does not collect a password, reprovision credentials, migrate keyrings, or
restart providers. The next provider start uses the refreshed settings.

On the other machine, pull these dotfiles and run the wizard there. A missing
TPM or an older systemd stops provisioning before the working provider changes.
Before activation, the shared Hyprland startup keeps using GNOME Keyring.

## Verify and recover

```sh
desktop-keyring status
./check-setup.sh keyring
journalctl --user -b -u oo7-daemon.service
```

Test a fresh password sign-in, a fresh fingerprint sign-in, lock/unlock, and
suspend/resume. Also test an application using libsecret and any Flatpak apps
that store secrets. The migration selects the standard Secret Service provider;
it does not rewrite existing portal backend preferences. If a Flatpak-specific
Secret portal is configured for GNOME Keyring, review that selection separately.

The automatic credential covers keyrings encrypted with the supplied password;
other collections with different passwords can still prompt.

To return to the previous provider:

```sh
desktop-keyring rollback
```

Rollback restores the exact saved provider configuration, stops/disables oo7
when this migration enabled it, reloads units, and restarts the previous GNOME
daemon configuration. It leaves the original files, the backup, the encrypted
credential and new oo7 data intact. Secrets added **after migration** exist in
oo7's V1 keyrings and are not automatically merged back into GNOME Keyring.

After changing the keyring password, refresh the sealed credential and restart
oo7 when convenient:

```sh
desktop-keyring provision
systemctl --user restart oo7-daemon.service
desktop-keyring status
```

Provisioning verifies the current V1 login keyring if present, otherwise the
original GNOME login keyring. It never writes an unencrypted keyring or a
plaintext password file. If TPM unsealing fails, rollback provides the old
password-based provider; it does not require a working TPM credential.

Implementation references: [oo7 0.7.3 server documentation](https://github.com/linux-credentials/oo7/blob/0.7.3/server/README.md),
[service unit](https://github.com/linux-credentials/oo7/blob/0.7.3/server/data/oo7-daemon.service.in),
[maturity assessment](../research/oo7-keyring-maturity.md).

Tests use disposable homes, copied fixtures and mocked service operations:

```sh
python -B -m unittest discover -s tests -p test_keyring.py -v
```

Additional opt-in tests exercise synthetic TPM credentials in a transient user
service (`ATELIER_TPM_TESTS=1`) and the real oo7 daemon on a private D-Bus session
(`ATELIER_OO7_DAEMON=/path/to/oo7-daemon` plus
`ATELIER_OO7_LEGACY_FIXTURE=/path/to/oo7-0.7.3/client/fixtures/legacy.keyring`).
The fixture password is the upstream test value, not an account password.
