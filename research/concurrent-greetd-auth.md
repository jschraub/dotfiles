# Concurrent greetd fingerprint and password authentication

Date: 2026-11-22. Scope: implementation research only. No packages, PAM files,
services, or authentication policy were changed.

## Recommendation

Use a PAM module that owns both the fprintd verification and the password
conversation, while leaving greetd as the only authority that creates the user
session. The best currently available candidate is the `LuvHakii` fork behind
the AUR package [`pam-fprint-grosshack-fork-git`](https://aur.archlinux.org/packages/pam-fprint-grosshack-fork-git),
but it is not mature enough to trust unreviewed:

- It is a September 2026, two-commit GitHub fork, not an upstream fprintd
  release. The repository metadata shows no release, no tests, zero stars, and
  no open issues ([repository metadata](https://api.github.com/repos/LuvHakii/pam-fprint-grosshack),
  [commit history](https://api.github.com/repos/LuvHakii/pam-fprint-grosshack/commits?per_page=20)).
- The AUR package tracks a moving `grosshack-1.94.x` branch, has zero votes,
  and is community maintained ([AUR package record](https://aur.archlinux.org/packages/pam-fprint-grosshack-fork-git)).
- It does fix the two defects found in the cloned v0.3.0 source: unlimited
  timeout uses an explicit `INT64_MAX` wait instead of converting
  `ULONG_MAX - now()` to `int64_t`, and the password helper has an eventfd,
  device release, join/timed-join, and abandoned-thread path
  ([fork source](https://github.com/LuvHakii/pam-fprint-grosshack/blob/grosshack-1.94.x/pam/pam_fprintd.c),
  [fork branch source](https://github.com/LuvHakii/pam-fprint-grosshack/tree/grosshack-1.94.x)).

Do not deploy the original AUR `pam-fprint-grosshack` v0.3.0 or its
`unlimited-timeout` variant. The original package has not changed since July
2022 ([AUR record](https://aur.archlinux.org/packages/pam-fprint-grosshack)),
and the upstream commit being evaluated is explicitly a 2022 fork of fprintd
1.94.2 ([commit `45b42524`](https://gitlab.com/mishakmak/pam-fprint-grosshack/-/commit/45b42524fb5783e1e555067743d7e0f70d27888a)).

The recommended implementation sequence is therefore:

1. Build and pin the fork at a reviewed commit in a local package. Do not
   follow a floating `-git` branch in the shared setup.
2. Put the module before `pam_unix.so try_first_pass` in the **user-login**
   PAM service, preserving the existing faillock/account/password/session
   policy. Keep the module optional on the readerless host, or install the
   same module there and rely on its no-device `PAM_AUTHINFO_UNAVAIL` fallback.
3. Add a dedicated PAM-side lid gate before the fingerprint module. Closed lid
   means skip fingerprint and run password-only; no lid means ordinary open
   behavior, which still falls back to password when no reader exists.
4. Accept the module only after the integration matrix below passes. This is a
   security-sensitive workaround, not a general replacement for fprintd PAM.

## Why greetd cannot do this natively

Current greetd has no concurrent-authentication capability:

- The IPC protocol exposes one `create_session`, one sequence of
  `auth_message` responses, and one `post_auth_message_response`; it does not
  expose a fingerprint event, second authentication channel, or authentication
  winner ([greetd IPC man page](https://github.com/kennylevinsen/greetd/blob/master/man/greetd-ipc-7.scd)).
- The session interface stores one pending message in `last_msg`; `get_state()`
  waits for the PAM worker and `post_response()` answers that same worker
  ([session interface](https://github.com/kennylevinsen/greetd/blob/master/greetd/src/session/interface.rs)).
- The PAM conversation sends one question over the worker socket and waits for
  one response before returning to PAM ([conversation implementation](https://github.com/kennylevinsen/greetd/blob/master/greetd/src/session/conv.rs)).
- The worker calls `pam_authenticate`, then `pam_acct_mgmt`, `pam_setcred`, and
  later `pam_open_session` and `pam_close_session` itself
  ([worker](https://github.com/kennylevinsen/greetd/blob/master/greetd/src/session/worker.rs),
  [PAM session wrapper](https://github.com/kennylevinsen/greetd/blob/master/greetd/src/pam/session.rs)).

Quickshell exposes the same single-channel model: `Greetd.respond()` may only
answer the current `authMessage`, while `readyToLaunch` is emitted only after
greetd authentication finishes ([official Greetd API](https://quickshell.org/docs/v0.3.2/types/Quickshell.Services.Greetd/Greetd/)).

Therefore, an ordinary PAM stack such as `pam_fprintd` followed by `pam_unix`
is necessarily serial. The upstream fprintd PAM documentation states the
limitation directly: simultaneous password/fingerprint input would require the
login manager to run two separate PAM stacks
([fprintd PAM README](https://gitlab.com/mishakmak/pam-fprint-grosshack/-/blob/45b42524fb5783e1e555067743d7e0f70d27888a/pam/README)).
That is not a greetd feature today.

## Grosshack v0.3.0 findings

The checked-out source is commit `45b42524fb5783e1e555067743d7e0f70d27888a`
in `/tmp/opencode/fprint-source`.

- `pam_sm_authenticate()` starts a password-prompt pthread, while the calling
  thread claims the fprintd device and runs `VerifyStart`/signal processing
  ([source, `do_auth`](https://gitlab.com/mishakmak/pam-fprint-grosshack/-/blob/45b42524fb5783e1e555067743d7e0f70d27888a/pam/pam_fprintd.c)).
- A password is put into `PAM_AUTHTOK`, and the module returns
  `PAM_AUTHINFO_UNAVAIL`; a following `pam_unix.so try_first_pass` can then
  validate that token. A fingerprint match returns `PAM_SUCCESS`, so a
  `sufficient` module can finish the auth phase.
- The original `timeout=-1` path stores `UINT_MAX`, leaves
  `verification_end=ULONG_MAX`, then computes `int64_t wait_time =
  verification_end - now()`. On Arch's 64-bit ABI the unsigned difference is
  outside `int64_t`; its conversion is not a valid infinite wait and commonly
  becomes negative, causing the scan loop to stop immediately.
- The original code calls `pthread_cancel()` without joining the prompt thread.
  `verify_data` and the PAM handle can consequently be torn down while the
  helper is still in `pam_prompt()` or `pam_set_item()`. The README itself
  warns that this is a hack with possible major security flaws
  ([original README](https://gitlab.com/mishakmak/pam-fprint-grosshack/-/blob/45b42524fb5783e1e555067743d7e0f70d27888a/README)).
- The cloned `meson.build` comments out the upstream test subdirectory and the
  repository contains no active tests for this concurrent path
  ([build file](https://gitlab.com/mishakmak/pam-fprint-grosshack/-/blob/45b42524fb5783e1e555067743d7e0f70d27888a/meson.build)).

The newer fork is materially better, not merely rebased. Its source explicitly
handles the unlimited wait, wakes the bus poll with `eventfd`, releases the
device before an unbounded password-thread wait, and uses `pthread_join()` or a
bounded `pthread_timedjoin_np()` path ([fork source](https://github.com/LuvHakii/pam-fprint-grosshack/blob/grosshack-1.94.x/pam/pam_fprintd.c)).
It still remains a cross-thread PAM-handle hack. In particular, the timed
abandon path is a residual risk for a GUI conversation that cannot cancel
prompting promptly. It needs adversarial testing with the actual Quickshell
conversation before production use.

## Alternatives assessed

| Option | Result | Reason |
| --- | --- | --- |
| Stock `pam_fprintd` before `pam_unix` | Reject | PAM modules run serially; password is not offered until fingerprint returns or times out. This is the current failure mode. |
| Original grosshack v0.3.0 | Reject | Stale, broken unlimited timeout, unjoined helper thread, disabled tests. |
| AUR `pam-fprint-grosshack-fork-git` | Candidate | Only found maintained implementation that retains one PAM auth call and addresses the known timeout/thread defects. Pin and audit it; do not consume its moving branch. |
| Quickshell `PamContext` for fingerprint plus greetd password | Reject | `PamContext` can run an independent PAM service, but a UI-side success does not satisfy greetd's PAM handle. Treating it as login proof bypasses the required greetd account/session path ([official PamContext API](https://quickshell.org/docs/v0.3.2/types/Quickshell.Services.Pam/PamContext/)). |
| UI-side fprintd match followed by `greetd.launch()` | Reject | `launch()` requires greetd's `ReadyToLaunch`; it cannot import another PAM context's success. This would be an authentication bypass, not concurrent greetd auth. |
| Custom greetd dual-PAM implementation | Correct long-term design, high cost | Add two independently cancellable auth handles, define the winning handle, and run account/session checks only on the winner. Requires a greetd design/patch and security review; no native capability or upstream implementation was found. |
| `pam_exec` lid script as the whole solution | Not sufficient | `pam_exec` can run a fixed command and its exit status can participate in PAM control flow, but it does not create concurrency and it has environment/TOCTOU concerns ([Linux-PAM pam_exec source](https://github.com/linux-pam/linux-pam/blob/master/modules/pam_exec/pam_exec.c), [pam_exec documentation](https://github.com/linux-pam/linux-pam/blob/master/modules/pam_exec/pam_exec.8.xml)). |

## Lid-closed and readerless policy

The UI cannot reliably choose this policy after `createSession()`: by then PAM
has already started the configured auth stack. The gate must be inside that
stack, before the grosshack module.

Preferred design: a small, root-owned, separately testable PAM policy module
reads the kernel lid state and returns a control result that skips only the
fingerprint module when the lid is closed. It must treat a machine with no lid
device as open, and must never read or expose `PAM_AUTHTOK`. The existing
password, faillock, account, and session lines remain authoritative.

`pam_exec` is technically capable of implementing the same jump with a fixed
absolute helper and no `expose_authtok`; PAM control syntax supports explicit
return-code jumps and missing optional modules ([Linux-PAM configuration
source](https://github.com/linux-pam/linux-pam/blob/master/doc/man/pam.conf.5.xml)).
It is not the preferred final design here because the helper's result is a
snapshot, lid state can change between modules, and the helper becomes part of
the root authentication boundary. If used as an interim experiment, it must be
an immutable absolute path, fixed environment, no shell, no user-controlled
arguments, fail closed to password-only on unreadable lid state, and have a
dedicated PAM test service. Do not use a shell one-liner or `expose_authtok`.

The shared repository can support both machines with one policy template:

- On the fingerprint machine, install the pinned module and enable the
  grosshack line behind the lid gate.
- On the readerless machine, either install the same module or use Linux-PAM's
  missing-module form (`-auth`) and let `pam_unix` authenticate. Validate this
  exact behavior in a disposable PAM service before changing the real login
  policy.
- Keep the stock password-only path as the recovery policy. A missing fprintd
  device must result in `PAM_AUTHINFO_UNAVAIL`, never an auth success.

Systemd-logind's lid settings control actions such as suspend and lock; they do
not select a PAM authentication stack ([systemd logind source](https://github.com/systemd/systemd/blob/main/man/logind.conf.xml)).
They are therefore not a substitute for the PAM-side gate.

## Acceptance blockers

Before adopting the candidate, test both machines and retain a TTY recovery
path:

- Type the password immediately, with no finger scan, and verify it succeeds
  before the fingerprint timeout.
- Leave the password prompt open, then match a finger; verify the helper exits,
  the fprintd device is released, and greetd reaches `ReadyToLaunch`.
- Exercise wrong password, wrong finger, retry, cancel, fprintd unavailable,
  no enrolled print, and prompt timeout. Confirm no stale prompt or PAM worker
  survives.
- Close the lid before authentication and verify no scan starts while password
  still works. Test open, closed-at-boot, resume-with-lid-closed, external
  display, and a machine with no lid device.
- On the readerless machine, test both module absent and module installed with
  no reader. Verify password login and that the module cannot turn absence into
  success.
- Verify invalid, locked, expired, and account-policy-restricted users are
  rejected after a fingerprint match. Verify greetd still performs account,
  credential, and session setup and teardown; the fingerprint match must not
  launch a session directly.
- Repeat failures enough to exercise the existing `pam_faillock` policy, then
  test a successful password and fingerprint path for correct counter reset.
- Inspect the journal and process tree for crashes, hangs, leaked helper
  threads, device claims, or password text. Test the oo7 keyring handoff only
  after greetd authentication/session behavior is correct.

## Primary sources

- [greetd repository](https://github.com/kennylevinsen/greetd)
- [greetd IPC protocol](https://github.com/kennylevinsen/greetd/blob/master/man/greetd-ipc-7.scd)
- [greetd session worker](https://github.com/kennylevinsen/greetd/blob/master/greetd/src/session/worker.rs)
- [Quickshell Greetd API](https://quickshell.org/docs/v0.3.2/types/Quickshell.Services.Greetd/Greetd/)
- [Quickshell PamContext API](https://quickshell.org/docs/v0.3.2/types/Quickshell.Services.Pam/PamContext/)
- [Original grosshack commit](https://gitlab.com/mishakmak/pam-fprint-grosshack/-/commit/45b42524fb5783e1e555067743d7e0f70d27888a)
- [Maintained fork source](https://github.com/LuvHakii/pam-fprint-grosshack/tree/grosshack-1.94.x)
- [AUR original package](https://aur.archlinux.org/packages/pam-fprint-grosshack)
- [AUR fork package](https://aur.archlinux.org/packages/pam-fprint-grosshack-fork-git)
- [Arch official fprintd package](https://archlinux.org/packages/extra/x86_64/fprintd/)
- [Linux-PAM pam_exec source](https://github.com/linux-pam/linux-pam/blob/master/modules/pam_exec/pam_exec.c)
- [Linux-PAM PAM configuration source](https://github.com/linux-pam/linux-pam/blob/master/doc/man/pam.conf.5.xml)
- [systemd logind configuration source](https://github.com/systemd/systemd/blob/main/man/logind.conf.xml)
