"""Atelier adapter and lifecycle tests. No desktop changes, passwords or sudo."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "hyprland-common/.local/bin/desktop-shell"
ADAPTER = ROOT / "quickshell/.config/quickshell/atelier/backend.py"
spec = importlib.util.spec_from_file_location("atelier", ADAPTER)
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


class AdapterTest(unittest.TestCase):
    @patch.object(backend, "command")
    def test_relative_volume_steps_do_not_depend_on_stale_ui_state(self, command):
        for delta, expected in [(5, "5%+"), (-5, "5%-"), (15, "15%+")]:
            backend.action(dict(action="volume-step", delta=delta))
            self.assertEqual(command.call_args.args[0], [
                "wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", expected,
            ])
        for invalid in ["5%; bad", 1, 0, 105, True]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                backend.action(dict(action="volume-step", delta=invalid))

    def test_audio_requests_are_applied_in_input_order(self):
        applied = []
        completed = threading.Event()
        def apply(request):
            if request["sequence"] == 1:
                time.sleep(0.04)
            applied.append(request["sequence"])
            if len(applied) == 3:
                completed.set()
        requests = "\n".join(json.dumps(dict(action=name, sequence=index))
                             for index, name in enumerate(["volume-step", "volume", "mute"], 1)) + "\n"
        backend.REFRESH.clear()
        with patch("sys.argv", ["backend.py"]), patch("sys.stdin", io.StringIO(requests)), \
                patch.object(backend, "handle", side_effect=apply), \
                patch.object(backend, "status", return_value={}), \
                patch.object(backend, "watch_hyprland"), patch.object(backend, "emit"):
            backend.main()
            self.assertTrue(completed.wait(1), "All fake audio operations must finish within the test")
        self.assertEqual(applied, [1, 2, 3])

    @unittest.skipUnless(importlib.util.find_spec("gi"), "PyGObject required for desktop-entry launch integration")
    def test_gio_launch_uses_a_real_desktop_entry_and_detached_streams(self):
        from gi.repository import GioUnix
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "launched"
            entry = root / "atelier-test.desktop"
            entry.write_text("[Desktop Entry]\nType=Application\nName=Atelier test\n"
                             f"Exec=/usr/bin/touch {marker}\nTerminal=false\n")
            app = GioUnix.DesktopAppInfo.new_from_filename(str(entry))
            self.assertIsNotNone(app)
            with patch.object(GioUnix.DesktopAppInfo, "new", return_value=app):
                backend.launch_app("atelier-test.desktop")
            deadline = time.monotonic() + 2
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(marker.exists())

    @patch.object(backend, "command", return_value="[]")
    def test_focus_events_only_refresh_fast_hyprland_state(self, command):
        self.assertEqual(set(backend.status(include_system=False)), {"window", "workspaces", "monitors"})
        self.assertEqual(command.call_count, 3)
        self.assertTrue(all(call.args[0][0] == "hyprctl" for call in command.call_args_list))

    def test_nmcli_escaping(self):
        self.assertEqual(backend.fields(r"*:90:WPA2:Room\:One\\Two"),
                         ["*", "90", "WPA2", "Room:One\\Two"])

    @patch.object(backend, "connections", return_value=[])
    @patch.object(backend, "command")
    def test_networks_are_deduplicated_and_current_ap_wins(self, command, profiles):
        command.return_value = "*:40:WPA2:Home\n:90:WPA2:Home\n:80::Guest"
        rows = backend.networks()["items"]
        self.assertEqual([r["ssid"] for r in rows], ["Home", "Guest"])
        self.assertTrue(rows[0]["connected"])
        self.assertEqual(rows[0]["signal"], 40)

    def test_battery_is_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(backend.batteries(root), [])
            battery = root / "BAT0"
            battery.mkdir()
            for name, value in [("type", "Battery"), ("capacity", "27"), ("status", "Charging")]:
                (battery / name).write_text(value)
            self.assertEqual(backend.batteries(root), [dict(name="BAT0", percent=27, status="Charging")])

    @patch.object(backend, "command")
    def test_workspace_uses_lua_and_validates_input(self, command):
        backend.action(dict(action="workspace", number=4))
        command.assert_called_once_with(["hyprctl", "dispatch", "hl.dsp.focus({ workspace = 4 })"])
        for value in [0, -1, "1); os.execute('bad')", 1000]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                backend.action(dict(action="workspace", number=value))

    @patch.object(backend, "command")
    def test_volume_is_capped_and_never_shell_evaluated(self, command):
        for requested, expected in [(-10, "0.000"), (150, "1.000"), (57, "0.570")]:
            backend.action(dict(action="volume", percent=requested))
            self.assertEqual(command.call_args.args[0][-1], expected)
        with self.assertRaises(ValueError):
            backend.action(dict(action="volume", percent="$(bad)"))

    @patch.object(backend, "detached")
    @patch.object(backend.shutil, "which", return_value="/usr/bin/protonvpn-app")
    def test_proton_remains_vpn_owner(self, which, detached):
        backend.action(dict(action="vpn", uuid="not-a-real-profile"))
        detached.assert_called_once_with(["protonvpn-app"])

    @patch.object(backend, "command")
    @patch.object(backend, "detached")
    def test_cast_keeps_amd_override(self, detached, command):
        backend.action(dict(action="open", target="cast"))
        detached.assert_called_once_with(["env", "LIBVA_DRIVER_NAME=radeonsi", "gnome-network-displays"])

    @patch.object(backend, "networks", return_value={"items": [dict(ssid="Home", security="WPA2", uuid="")]})
    @patch.object(backend, "connections", return_value=[])
    @patch.object(backend, "command")
    @patch.object(backend, "optional", return_value="full")
    def test_wifi_password_only_uses_stdin(self, optional, command, profiles, networks):
        backend.connect_wifi(dict(ssid="Home", password="super secret"))
        args, kwargs = command.call_args
        self.assertNotIn("super secret", " ".join(args[0]))
        self.assertEqual(kwargs["data"], "super secret\n")
        self.assertIn("--ask", args[0])
        self.assertIn("name", args[0])

    @patch.object(backend, "networks", return_value={"items": [dict(ssid="Home", security="WPA2", uuid="saved")]})
    @patch.object(backend, "connections", return_value=[])
    @patch.object(backend, "command")
    @patch.object(backend, "optional", return_value="full")
    def test_saved_wifi_profile_uses_uuid(self, optional, command, profiles, networks):
        backend.connect_wifi(dict(ssid="Home"))
        self.assertEqual(command.call_args.args[0][-2:], ["uuid", "saved"])
        self.assertNotIn("data", command.call_args.kwargs)

    @patch.object(backend, "networks", return_value={"items": [dict(ssid="Home", security="WPA2", uuid="")]})
    @patch.object(backend.uuid, "uuid4")
    @patch.object(backend, "connections")
    @patch.object(backend, "command", side_effect=subprocess.CalledProcessError(1, "nmcli"))
    @patch.object(backend, "optional", return_value="Home")
    def test_failed_wifi_only_cleans_own_new_profile(self, optional, command, profiles, uuid, networks):
        uuid.return_value.hex = "ours"
        profiles.side_effect = [[dict(uuid="existing")], [
            dict(uuid="existing", name="Atelier ours", type="802-11-wireless"),
            dict(uuid="concurrent", name="Someone else", type="802-11-wireless"),
            dict(uuid="new", name="Atelier ours", type="802-11-wireless"),
        ]]
        with self.assertRaisesRegex(ValueError, "Could not connect"):
            backend.connect_wifi(dict(ssid="Home", password="wrong"))
        deletes = [call.args[0] for call in optional.call_args_list if "delete" in call.args[0]]
        self.assertEqual(deletes, [["nmcli", "connection", "delete", "uuid", "new"]])

    @patch.object(backend, "action", side_effect=ValueError("Connection failed"))
    def test_result_does_not_echo_secrets_and_request_is_cleared(self, action):
        request = dict(action="connect", password="do-not-print")
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            backend.handle(request)
            self.assertNotIn("do-not-print", output.getvalue())
            self.assertFalse(json.loads(output.getvalue())["data"]["ok"])
        self.assertEqual(request, {})

    @patch.object(backend, "command")
    @patch.object(backend, "detached")
    @patch.object(backend.shutil, "which", return_value=None)
    def test_logout_restores_displays_before_exit(self, which, detached, command):
        backend.action(dict(action="power", choice="logout"))
        self.assertEqual(command.call_args_list[0].args[0][-1], "--all-on")
        self.assertEqual(command.call_args_list[1].args[0], ["hyprctl", "dispatch", "hl.dsp.exit()"])

    def test_unknown_actions_cannot_execute_arbitrary_commands(self):
        with self.assertRaises(ValueError):
            backend.action(dict(action="exec", command="anything"))
        with self.assertRaises(KeyError):
            backend.action(dict(action="open", target="anything"))


class LifecycleTest(unittest.TestCase):
    def test_native_start_is_idempotent_and_failure_never_launches_legacy(self):
        for fail in [False, True]:
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                binary = home / "bin"
                binary.mkdir()
                config = home / ".config/quickshell/atelier/shell.qml"
                config.parent.mkdir(parents=True)
                config.write_text("// simulated by fake qs")
                commands = {
                    "qs": '''#!/bin/bash
if [[ "$1" == kill ]]; then exit 0; fi
if [[ "$1" == ipc ]]; then [[ -f "$HOME/started" ]] && echo ready; exit 0; fi
[[ -z "${ATELIER_PREVIEW:-}" && -z "${ATELIER_TEST:-}" ]] || exit 3
echo launch >> "$CALLS"
[[ "$FAIL_QS" == 0 ]] && touch "$HOME/started"
exit "$FAIL_QS"
''',
                    "pgrep": "#!/bin/sh\nexit 1\n",
                    "pkill": '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n',
                    "gdbus": "#!/bin/sh\necho quickshell\n",
                    "busctl": '#!/bin/sh\necho "$*" >> "$CALLS"\necho quickshell\n',
                    "systemctl": "#!/bin/sh\nexit 1\n",
                    "systemd-cat": "#!/bin/sh\nexit 0\n",
                    "swaync": '#!/bin/sh\necho forbidden >> "$CALLS"\n',
                    "waybar": '#!/bin/sh\necho forbidden >> "$CALLS"\n',
                }
                for name, script in commands.items():
                    file = binary / name
                    file.write_text(script)
                    file.chmod(0o755)
                calls = home / "calls"
                env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                           XDG_RUNTIME_DIR=str(home),
                           PATH=f'{binary}:{os.environ["PATH"]}', ATELIER_QS_BINARY=str(binary / "qs"),
                           FAIL_QS=str(int(fail)), CALLS=str(calls), ATELIER_PREVIEW="1", ATELIER_TEST="1")
                result = subprocess.run([str(SHELL), "activate"], env=env, text=True,
                                        capture_output=True, timeout=5)
                self.assertEqual(result.returncode, int(fail), result.stderr)
                self.assertNotIn('forbidden', calls.read_text())
                self.assertFalse((home / '.config/dotfiles/desktop-shell').exists())
                if not fail:
                    subprocess.run([str(SHELL), 'start'], env=env, check=True, capture_output=True)
                    self.assertEqual(calls.read_text().splitlines().count('launch'), 1)
                    self.assertIn('--auto-start=no', calls.read_text())

    def test_mode_is_always_native_and_legacy_command_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([str(SHELL), "mode"], env=dict(os.environ,
                                    HOME=directory, XDG_CONFIG_HOME=directory),
                                    text=True, capture_output=True, check=True)
            self.assertEqual(result.stdout.strip(), "quickshell")
            result = subprocess.run([str(SHELL), "legacy"], env=dict(os.environ,
                                     HOME=directory, XDG_CONFIG_HOME=directory),
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)

    def test_new_shell_is_default_and_legacy_is_retired(self):
        result = subprocess.run(["bash", "-c", "source ./setup.sh; default_items"],
                                cwd=ROOT, text=True, capture_output=True, check=True)
        names = result.stdout.splitlines()
        self.assertIn("quickshell", names)
        for legacy in ["waybar", "wofi", "wlogout"]:
            self.assertNotIn(legacy, names)

    def test_quickshell_dry_run_has_no_install_or_activation(self):
        result = subprocess.run(["bash", "setup.sh", "--dry-run", "quickshell"],
                                cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertIn("would stow: quickshell", result.stdout)
        self.assertIn("Activate when ready", result.stdout)


if __name__ == "__main__":
    unittest.main()
