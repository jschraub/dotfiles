# Screen sharing to Apple TV, Miracast and Chromecast

**Super+Ctrl+S**, or Connectivity → Screen sharing, opens the Atelier panel.
No receiver app is needed on an Apple TV. It uses AirPlay. Miracast and Google
Cast receivers use GNOME Network Displays, not the AirPlay sender.

## Install on either machine

Run as your normal user:

```sh
./setup.sh casting
```

This optional setup item installs Doubletake's `doubletake-bin` AUR package and
the GStreamer/audio/portal dependencies, restows the shell, and records that
casting is installed. Review the AUR package and normal package-manager prompts.
`libfdk-aac` is the Arch package name, despite upstream examples naming `fdk-aac`.
Initial `setup.sh all` does not add this experimental backend. Routine updates
include its requirements/audit only after its marker is installed.

Setup does not connect to a receiver, enable a Doubletake systemd service at login,
install/replace GPU drivers, alter monitor profiles, or change firewall/router
policy. Current control-protocol support is **Doubletake 0.6.x**, reviewed against
release `v0.6.0`; other versions are refused at startup pending review.

## AirPlay to an Apple TV

1. Wake the Apple TV, enable AirPlay, and put it on the same reachable LAN as the
   sender. Guest isolation and VLAN boundaries can prevent mDNS discovery.
2. Open Screen sharing. Start at **Auto encoder, 1080p, audio off**.
3. Click **Find AirPlay devices**. Discovery runs only after this action. Devices
   update as Doubletake discovers them; nothing selects the first TV automatically.
4. Select the named receiver. Enter its on-screen PIN or configured receiver
   password in the panel. The stream uses the discovered receiver identity as well
   as its IP, so saved-pairing identity checks are not bypassed.
5. Use the compositor's screencast portal to select a capture source. The portal
   can remember prior selections. Explicitly starting the cast is still required.
6. Confirm the image on the TV, then try computer audio if desired. Stop before
   changing encoder/resolution/audio options. Audio copies the current default
   output, preserving local playback; the microphone is never selected by this UI.

The default is H.264 / 30 fps. “Receiver maximum” requests the maximum usable
H.264 canvas; it is not a promise of 4K, HEVC or HDR. This first integration allows
one AirPlay receiver at a time. It does not attempt synchronized multiroom playback.

The topbar shows **AirPlay discovery**, **AirPlay setup**, or **AirPlay streaming**
according to the owned sender's state. It also reports the actual encoder and
hardware/software status supplied by Doubletake. A plugin availability check is
not proof of a working capture/encode session.

**Stop sharing** ends this helper's owned AirPlay and Network Displays processes.
Closing the panel leaves an intentional session running. Helper/QML reload,
owner death or logout stops owned sender processes; no previous stream is restored
by the new helper. Do not restart Quickshell to troubleshoot an active presentation
unless you intend to end it. Stop sharing before handling private material,
locking or suspending. No lock, PAM or suspend policy was modified.

## NVIDIA / Framework Laptop 16

There is no forced `LIBVA_DRIVER_NAME=radeonsi` on the new or legacy cast launch.
The default `auto` selection lets Doubletake choose an available encoder. Its
explicit `nvenc` preference uses the NVIDIA path, including upstream's Vulkan
fallback; `vaapi` is the Intel/AMD preference; `none` requests x264 software.
The screen source still comes through the Wayland portal and can be on a different
GPU from the encoder. Hybrid DMA-BUF conversion is hardware/driver dependent.
Owned sender processes clear the inherited `LIBVA_DRIVER_NAME` so mini-mecha's
session-wide NVIDIA VA decode driver does not get forced onto AMD capture
conversion. This is process-local; the laptop's Hyprland GPU environment is
unchanged, and selecting NVENC still uses the NVIDIA encode path.

Use **Check encoders** to inspect installed GStreamer elements:

- `nvh264enc`: NVIDIA NVENC; requires working NVIDIA userspace encode libraries
  and a supported GPU/driver.
- `vulkanh264enc`: upstream Vulkan H.264 fallback where supported.
- `vah264enc`: Intel/AMD VA-API.
- `x264enc`: software fallback.
- `pipewiresrc` / `pulsesrc`: Wayland video / output audio.

`gst-plugins-bad` provides the relevant encoder plugins in this Arch setup.
Existing machine-appropriate NVIDIA driver packages remain your responsibility;
do not install an arbitrary driver branch over the Framework's working driver.
`gst-plugin-va` is also retained for AMD/Intel capture conversion on hybrid systems.
Hyprland requires `xdg-desktop-portal-hyprland >= 1.5.0` per Doubletake's compatibility
notes. The audit checks generic backends/plugins, not the presence of an AMD-only
or NVIDIA-only driver on every machine.

**NVIDIA hardware has not been physically tested by the automated suite.**
On the Framework, test Auto, then explicitly NVIDIA and verify the reported
encoder and the real TV image/audio. Test Software if the hardware path fails.
The local oki-mecha diagnostics found VA-API, Vulkan H.264, software and portal
elements; that does not validate the Framework's NVENC pipeline.

## Miracast / Chromecast

**Open Network Displays** launches the existing application without a vendor
override. Receiver discovery, pairing, screen selection and audio routing stay
in that application's UI. AirPlay audio/encoder/resolution controls do not apply
to this path. **Sharing app open** means the application is running, not that a
receiver is connected.

Miracast requires compatible Wi-Fi Direct hardware/driver/NetworkManager support.
Chromecast normally uses the existing LAN. An Apple TV does not become a Miracast
or Google Cast receiver by enabling AirPlay.

An already-running external Network Displays instance is not adopted or killed.
Close/manage it separately before launching an owned instance. If an application
delegates to another instance during a startup race, Atelier reports that state
as unknown rather than claiming it can stop the external session.

## Privacy and networking

Doubletake sends directly to the receiver over the network, not through a cloud
relay. It is **experimental**, and upstream explicitly discourages security-
sensitive use. Use trusted home receivers/networks and inspect what you share.
DRM-protected video can be black; use native TV apps for protected services.

- Pairing PINs/passwords use a dedicated QML-to-helper stdin pipe and the owned
  daemon's private Unix socket. They never enter generic desktop actions, argv,
  public shell IPC, or shell logs. The field clears on submit, receiver change
  and panel destruction. Background status refresh does not clear partial input.
- Pairing credentials use Secret Service via `-cred-backend keyring`. A locked/
  unavailable keyring fails the operation; there is no silent plaintext fallback.
- The daemon uses an owner-private temporary runtime directory, socket ownership
  and peer-PID checks, fixed argument lists, bounded control messages, and no
  automatic reconnection after helper restart. Only explicitly discovered private/
  link-local unicast receiver addresses are accepted by this first version.
- Sender output is discarded, upstream error bodies are not echoed, and inherited
  debug-file/code environment variables are removed from owned children.
- The helper reserves UDP **60000–60010** for AirPlay timing/audio. A default-deny
  host firewall can require an inbound rule scoped to the receiver IP and this
  range. No rule is installed automatically. mDNS/discovery policy is separate.
  Router port forwarding and Internet exposure are neither needed nor configured.
- No UPnP setup, authentication enrollment, trust-policy bypass or autostart
  Doubletake service is installed.

## Validate before relying on it

```sh
python3 -B quickshell/.config/quickshell/atelier/sharing.py --check
./check-setup.sh --machine mini-mecha casting   # use oki-mecha on the desktop
```

The read-only audit reports **UNKNOWN casting runtime** until a human verifies
the receiver, GPU, portal, pairing, audio and Stop behavior. A diagnostic pass
does not authenticate, discover receivers, capture the screen or stream media.

Automated tests use fake sender processes, private sockets and fake panel state:

```sh
ATELIER_GUI_TESTS=1 python3 -B -m unittest discover -s tests -p test_sharing.py
```

The Apple TV / Framework hardware matrix remains a manual test, including network
loss, driver errors, cancellation of the portal picker, and suspend/resume.

### Reviewed upstream contract

- [Doubletake v0.6.0 manual](https://github.com/omarroth/doubletake/blob/v0.6.0/man/man1/doubletake.1)
- [Daemon request/response structs and handlers](https://github.com/omarroth/doubletake/blob/v0.6.0/internal/daemon/daemon.go)
- [Compatibility and encoder requirements](https://github.com/omarroth/doubletake/blob/v0.6.0/docs/compatibility.md)
- [GNOME Network Displays](https://gitlab.gnome.org/GNOME/gnome-network-displays)
