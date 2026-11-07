#!/usr/bin/env python3
"""Atelier's narrow system adapter. JSON lines on stdin/stdout; never a shell.

Qt owns presentation and notifications. This adapter preserves the existing Lua
Hyprland, NetworkManager, Gio desktop-entry and logind integration policies.
"""
import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid


HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
HELPERS = HOME / ".local/bin"
PROBE = "http://nmcheck.gnome.org/check_network_status.txt"
OUTPUT_LOCK = threading.Lock()
NETWORK_LOCK = threading.Lock()
REFRESH = threading.Event()
REFRESH_SYSTEM = threading.Event()


def command(args, *, data=None, timeout=5):
    return subprocess.run(args, input=data, capture_output=True, text=True,
                          timeout=timeout, check=True).stdout.rstrip("\n")


def optional(args, default="", **kwargs):
    try:
        return command(args, **kwargs)
    except (OSError, subprocess.SubprocessError):
        return default


def emit(kind, data):
    with OUTPUT_LOCK:
        print(json.dumps({"type": kind, "data": data}), flush=True)


def fields(line):
    """Decode nmcli's escaped colon/backslash format without splitting SSIDs."""
    result, value, escaped = [], "", False
    for char in line:
        if escaped:
            value += char
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            result.append(value)
            value = ""
        else:
            value += char
    result.append(value)
    return result


def connections(active=False):
    args = ["nmcli", "-t", "-f", "NAME,UUID,TYPE", "connection", "show"]
    if active:
        args.append("--active")
    return [dict(zip(("name", "uuid", "type"), fields(line)))
            for line in command(args).splitlines() if len(fields(line)) == 3]


def network_state():
    devices = [fields(line) for line in command(
        ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"]).splitlines()]
    connected = next((d for d in devices if len(d) == 4 and d[2] == "connected"
                      and d[1] in ("wifi", "ethernet")), None)
    vpns = [c for c in connections(True) if c["type"] in ("vpn", "wireguard")]
    address = optional(["nmcli", "-g", "IP4.ADDRESS", "device", "show", connected[0]]) if connected else ""
    label, signal = connected[3] if connected else "Offline", None
    if connected and connected[1] == "wifi":
        for line in optional(["nmcli", "-t", "-f", "IN-USE,SIGNAL,SSID", "device", "wifi", "list", "--rescan", "no"]).splitlines():
            values = fields(line)
            if len(values) == 3 and values[0] == "*":
                label, signal = values[2], int(values[1])
                break
    return {"label": label, "address": address, "signal": signal,
            "kind": connected[1] if connected else "offline",
            "wifi": command(["nmcli", "radio", "wifi"]) == "enabled",
            "connectivity": command(["nmcli", "-t", "networking", "connectivity"]),
            "vpn": vpns[0]["name"] if vpns else ""}


def networks():
    profiles = connections()
    saved = {}
    for profile in profiles:
        if profile["type"] == "802-11-wireless":
            ssid = optional(["nmcli", "--escape", "no", "-g", "802-11-wireless.ssid", "connection", "show",
                             "uuid", profile["uuid"]])
            if ssid:
                saved[ssid] = profile["uuid"]
    best = {}
    raw = command(["nmcli", "-t", "-f", "IN-USE,SIGNAL,SECURITY,SSID", "device", "wifi",
                   "list", "--rescan", "no"])
    for line in raw.splitlines():
        parts = fields(line)
        if len(parts) != 4 or not parts[3]:
            continue
        used, signal, security, ssid = parts
        current = used == "*"
        row = {"ssid": ssid, "signal": int(signal), "security": security,
               "connected": current, "uuid": saved.get(ssid, "")}
        previous = best.get(ssid)
        if previous is None or (current, int(signal)) > (previous["connected"], previous["signal"]):
            best[ssid] = row
    return {"items": sorted(best.values(), key=lambda n: (
        not n["connected"], not bool(n["uuid"]), -n["signal"], n["ssid"])),
        "vpns": [p for p in profiles if p["type"] in ("vpn", "wireguard")],
        "proton": bool(shutil.which("protonvpn-app"))}


def batteries(root=Path("/sys/class/power_supply")):
    result = []
    for device in root.glob("*"):
        try:
            if (device / "type").read_text().strip() == "Battery":
                result.append({"name": device.name,
                               "percent": int((device / "capacity").read_text()),
                               "status": (device / "status").read_text().strip()})
        except (OSError, ValueError):
            continue
    return result


def audio_state(target="@DEFAULT_AUDIO_SINK@"):
    volume = optional(["wpctl", "get-volume", target])
    match = re.fullmatch(r"Volume:\s+(\d+(?:\.\d+)?)\s*(\[MUTED\])?", volume)
    return {"percent": round(float(match[1]) * 100), "muted": bool(match[2])} if match else None


def wallpaper_path():
    selected = os.environ.get("ATELIER_WALLPAPER_CONFIG")
    if not selected:
        profile = str((CONFIG / "hypr/hyprland.lua").resolve())
        selected = CONFIG / "hypr" / ("hyprpaper-oki-mecha.conf" if "hyprland-oki-mecha" in profile else "hyprpaper.conf")
    try:
        text = Path(selected).expanduser().read_text()
        match = re.search(r"^\s*path\s*=\s*(.+?)\s*$", text, re.MULTILINE)
        path = Path(os.path.expandvars(match[1])).expanduser() if match else None
        return str(path.resolve()) if path and path.is_file() else ""
    except OSError:
        return ""


def status(include_system=True):
    state = {}
    queries = {
        "monitors": lambda: json.loads(command(["hyprctl", "-j", "monitors"])),
        "workspaces": lambda: json.loads(command(["hyprctl", "-j", "workspaces"])),
        "window": lambda: json.loads(command(["hyprctl", "-j", "activewindow"])),
    }
    if include_system:
        queries.update({
            "network": network_state,
            "awake": lambda: json.loads(command([str(HELPERS / "dotfiles-keep-awake.sh"), "status"])),
            "wallpaper": wallpaper_path,
        })
    # Explicit unavailable state; never display a failed read as healthy/muted/off.
    for key, read in queries.items():
        try:
            state[key] = read()
        except (OSError, subprocess.SubprocessError, ValueError):
            state[key] = None
    if not include_system:
        return state
    state["audio"] = audio_state()
    state["microphone"] = audio_state("@DEFAULT_AUDIO_SOURCE@")
    state["battery"] = batteries()
    bluetooth = optional(["bluetoothctl", "show"])
    devices = optional(["bluetoothctl", "devices", "Connected"])
    connected = []
    for line in devices.splitlines():
        parts = line.split(" ", 2)
        if len(parts) != 3:
            continue
        info = optional(["bluetoothctl", "info", parts[1]])
        battery = re.search(r"Battery Percentage:.*\((\d+)\)", info)
        connected.append(parts[2] + (f"\u2003{battery[1]}% battery" if battery else ""))
    state["bluetooth"] = {"powered": "Powered: yes" in bluetooth, "connected": connected}
    return state


def app_entries():
    from gi.repository import Gio
    result = []
    for app in Gio.AppInfo.get_all():
        if not app.should_show() or not app.get_id():
            continue
        icon = app.get_icon()
        result.append({"id": app.get_id(), "name": app.get_display_name(),
                       "description": app.get_description() or "",
                       "icon": icon.to_string() if icon else "application-x-executable",
                       "keywords": " ".join(app.get_keywords() or []) if hasattr(app, "get_keywords") else ""})
    return sorted(result, key=lambda a: (a["name"].casefold(), a["id"]))


def launch_app(identifier):
    from gi.repository import GioUnix, GLib
    # Resolve an ID, not a path/command from QML. Gio handles desktop Exec field
    # codes, quoting, DBus activation and Terminal entries via xdg-terminal-exec.
    if not identifier.endswith(".desktop") or "/" in identifier or "\n" in identifier:
        raise ValueError("Invalid desktop application ID")
    app = GioUnix.DesktopAppInfo.new(identifier)
    if app is None or not app.should_show():
        raise ValueError("Application is no longer available")
    try:
        # Spawned applications must not inherit the shell's JSON protocol pipes.
        # This Gio API retains desktop-entry/DBus/Terminal semantics while routing
        # their standard streams away from the adapter.
        with open(os.devnull, "r+b") as null:
            if not app.launch_uris_as_manager_with_fds(
                [], None, GLib.SpawnFlags.SEARCH_PATH, None, None, None, None,
                null.fileno(), null.fileno(), null.fileno(),
            ):
                raise ValueError("Application could not be launched")
    except GLib.Error:
        raise ValueError("Application could not be launched. Check its desktop entry or terminal configuration.") from None


def keybindings():
    source = CONFIG / "hypr/scripts/keybindings.py"
    spec = importlib.util.spec_from_file_location("binding_reference", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for binding in json.loads(command(["hyprctl", "-j", "binds"])):
        key = binding.get("key") or f'keycode:{binding.get("keycode", 0)}'
        mods = [name for mask, name in module.MODIFIERS if binding.get("modmask", 0) & mask]
        flags = [name for field, name in (("release", "on release"), ("repeat", "repeat"),
                 ("locked", "works when locked")) if binding.get(field)]
        if binding.get("submap"):
            flags.append("submap: " + binding["submap"])
        rows.append({"key": " + ".join(mods + [module.KEY_NAMES.get(key, key)]),
                     "description": binding.get("description") or binding.get("dispatcher", ""),
                     "category": module.category_for(binding), "context": ", ".join(flags)})
    order = {name: index for index, name in enumerate(module.CATEGORIES)}
    return sorted(rows, key=lambda b: order[b["category"]])


def portal():
    if any(c["type"] in ("vpn", "wireguard") for c in connections(True)):
        emit("notice", "VPN is active; the network sign-in page may not load. Manage it in the VPN app.")
    detached(["zen-browser", "--new-window", PROBE])


def detached(args):
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def connect_wifi(request):
    # Re-read trusted system state; do not trust a stale UI row's security/profile.
    with NETWORK_LOCK:
        row = next((n for n in networks()["items"] if n["ssid"] == request.get("ssid")), None)
        if not row:
            raise ValueError("Network is no longer in range. Rescan and try again.")
        before = {p["uuid"] for p in connections()}
        profile_name = "Atelier " + uuid.uuid4().hex
        try:
            if row["uuid"]:
                command(["nmcli", "--wait", "20", "connection", "up", "uuid", row["uuid"]], timeout=25)
            else:
                password = request.get("password", "")
                if row["security"] and not password:
                    raise ValueError("A password is required")
                if "\n" in password or "\r" in password:
                    raise ValueError("Password must be a single line")
                command(["nmcli", "--wait", "20", "--ask", "device", "wifi", "connect", row["ssid"], "name", profile_name],
                        data=password + "\n", timeout=25)
        except (subprocess.SubprocessError, ValueError):
            # Delete ONLY profiles created by this attempt, never a pre-existing
            # profile with the same display name or SSID.
            if not row["uuid"]:
                for profile in connections():
                    if (profile["uuid"] not in before and profile["type"] == "802-11-wireless"
                            and profile["name"] == profile_name):
                        ssid = optional(["nmcli", "--escape", "no", "-g", "802-11-wireless.ssid", "connection", "show",
                                         "uuid", profile["uuid"]])
                        if ssid == row["ssid"]:
                            optional(["nmcli", "connection", "delete", "uuid", profile["uuid"]])
            raise ValueError("Could not connect. Check the password, or use Advanced for enterprise/hidden networks.") from None
        for _ in range(6):
            connectivity = optional(["nmcli", "-t", "networking", "connectivity", "check"], timeout=10)
            if connectivity in ("portal", "limited"):
                portal()
                break
            if connectivity == "full":
                break
            time.sleep(1)


def action(request):
    name = request.get("action")
    if name == "apps":
        emit("apps", app_entries())
    elif name == "bindings":
        emit("bindings", keybindings())
    elif name == "networks":
        emit("networks", networks())
    elif name == "launch":
        launch_app(str(request.get("id", "")))
    elif name == "workspace":
        number = int(request.get("number", 0))
        if not 1 <= number <= 999:
            raise ValueError("Invalid workspace")
        command(["hyprctl", "dispatch", f"hl.dsp.focus({{ workspace = {number} }})"])
    elif name == "volume":
        percent = max(0, min(100, float(request["percent"])))
        command(["wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", f"{percent / 100:.3f}"])
    elif name == "volume-step":
        delta = request.get("delta")
        if type(delta) is not int or not delta or abs(delta) > 100 or delta % 5:
            raise ValueError("Volume steps must be multiples of 5 between -100 and 100")
        command(["wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@",
                 f"{abs(delta)}%{'+' if delta > 0 else '-'}"])
    elif name == "mute":
        command(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
    elif name == "mic-mute":
        command(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"])
    elif name == "mic-volume":
        percent = max(0, min(100, float(request["percent"])))
        command(["wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SOURCE@", f"{percent / 100:.3f}"])
    elif name == "awake":
        command([str(HELPERS / "dotfiles-keep-awake.sh"), "toggle"], timeout=10)
    elif name == "connect":
        connect_wifi(request)
        emit("networks", networks())
    elif name == "rescan":
        with NETWORK_LOCK:
            command(["nmcli", "device", "wifi", "rescan"], timeout=20)
        emit("networks", networks())
    elif name == "wifi":
        command(["nmcli", "radio", "wifi", "on" if request.get("enabled") is True else "off"])
    elif name == "vpn":
        if shutil.which("protonvpn-app"):
            detached(["protonvpn-app"])
        else:
            uuid = str(request.get("uuid", ""))
            if not any(c["uuid"] == uuid and c["type"] in ("vpn", "wireguard") for c in connections()):
                raise ValueError("Choose a saved VPN profile")
            active = any(c["uuid"] == uuid for c in connections(True))
            command(["nmcli", "--wait", "20", "connection", "down" if active else "up", "uuid", uuid], timeout=25)
    elif name == "portal":
        portal()
    elif name == "open":
        targets = {"audio": ["pavucontrol"], "bluetooth": ["blueman-manager"],
                   "network": ["ghostty", "--title=nmtui-float", "-e", "nmtui"],
                   "cast": ["env", "LIBVA_DRIVER_NAME=radeonsi", "gnome-network-displays"]}
        detached(targets[request["target"]])
    elif name == "power":
        targets = {"lock": [str(CONFIG / "hypr/scripts/lock.sh")],
                   "reboot": ["systemctl", "reboot"], "shutdown": ["systemctl", "poweroff"]}
        choice = request.get("choice")
        if choice == "logout":
            command([str(CONFIG / "hypr/scripts/lid-display.sh"), "--all-on"])
            if shutil.which("hyprshutdown"):
                detached(["hyprshutdown"])
            else:
                command(["hyprctl", "dispatch", "hl.dsp.exit()"])
        else:
            detached(targets[choice])
    else:
        raise ValueError("Unknown shell action")


def handle(request):
    try:
        action(request)
        if request.get("action") in ("volume-step", "mute", "mic-mute"):
            mic = request["action"] == "mic-mute"
            value = audio_state("@DEFAULT_AUDIO_SOURCE@" if mic else "@DEFAULT_AUDIO_SINK@")
            if value:
                emit("osd", {"kind": "microphone" if mic else "volume", **value})
        emit("result", {"action": request.get("action"), "ok": True})
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, ImportError) as error:
        # CalledProcessError's repr includes argv; don't expose request payloads.
        message = str(error) if isinstance(error, ValueError) else "Action failed. Check the service or use advanced settings."
        emit("result", {"action": request.get("action"), "ok": False, "message": message})
    finally:
        request.clear()  # including any password
        REFRESH_SYSTEM.set()
        REFRESH.set()


def watch_hyprland(stop):
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not signature:
        return
    path = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "hypr" / signature / ".socket2.sock"
    while not stop.is_set():
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.connect(str(path))
                with connection.makefile("rb") as events:
                    for line in events:
                        if line.startswith((b"activewindow", b"windowtitle", b"focusedmon", b"workspace", b"createworkspace",
                                            b"destroyworkspace", b"movewindow", b"openwindow", b"closewindow", b"monitor")):
                            REFRESH.set()
                        if stop.is_set():
                            return
        except OSError:
            pass
        stop.wait(2)


def main():
    if sys.argv[1:] == ["--snapshot"]:
        print(json.dumps(status()))
        return
    if sys.argv[1:]:
        raise SystemExit("Usage: backend.py [--snapshot]")
    stop = threading.Event()
    def receive():
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool, \
                    concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="atelier-audio") as audio_pool:
                for line in sys.stdin:
                    try:
                        request = json.loads(line)
                        if not isinstance(request, dict):
                            raise ValueError()
                        # Preserve audio input order, including relative steps,
                        # absolute slider writes and mute; never race wpctl reads.
                        target = audio_pool if request.get("action") in ("volume", "volume-step", "mute", "mic-mute", "mic-volume") else pool
                        target.submit(handle, request)
                    except (ValueError, TypeError):
                        emit("notice", "Invalid shell request")
        finally:
            # Executor contexts drain their work BEFORE signalling main to exit.
            stop.set()
            REFRESH.set()
    threading.Thread(target=receive, daemon=True).start()
    threading.Thread(target=watch_hyprland, args=(stop,), daemon=True).start()
    state, last_system = {}, 0
    while not stop.is_set():
        now = time.monotonic()
        include_system = now - last_system >= 2 or REFRESH_SYSTEM.is_set()
        REFRESH_SYSTEM.clear()
        state.update(status(include_system))
        if include_system:
            last_system = now
        emit("state", state)
        REFRESH.wait(max(0.05, 2 - (time.monotonic() - last_system)))
        REFRESH.clear()


if __name__ == "__main__":
    main()
