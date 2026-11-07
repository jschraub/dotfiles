"""Opt-in QML/IPC smoke tests. No cutover or system-setting changes.

Adds temporary panels. The hover regression moves/restores the real pointer.

ATELIER_GUI_TESTS=1 python -B -m unittest discover -s tests -p test_atelier_gui.py
Can use ATELIER_QS_BINARY for an isolated Quickshell build.
"""
import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "quickshell/.config/quickshell/atelier"
QS = os.environ.get("ATELIER_QS_BINARY", shutil.which("qs") or "qs")


@unittest.skipUnless(os.environ.get("ATELIER_GUI_TESTS") == "1", "opt-in: opens temporary preview panels")
class AtelierGuiTest(unittest.TestCase):
    def test_workspace_numbers_fit_and_are_visually_centered(self):
        env = dict(os.environ, QT_QPA_PLATFORM="wayland")
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode="w+") as log:
            config = Path(directory) / "atelier"
            shutil.copytree(CONFIG, config)
            shutil.copyfile(ROOT / "tests/atelier-workspaces.qml", config / "workspace-test.qml")
            process = subprocess.Popen([QS, "-p", str(config / "workspace-test.qml"), "--no-color"],
                                       env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    response = subprocess.run([QS, "ipc", "--pid", str(process.pid), "call", "test", "status"],
                                              env=env, text=True, capture_output=True, timeout=5)
                    if process.poll() is not None or (response.returncode == 0 and json.loads(response.stdout)["width"] > 600):
                        break
                    time.sleep(0.05)
                self.assertIsNone(process.poll())
                sample = json.loads(response.stdout)
                for entry in sample["entries"]:
                    with self.subTest(workspace=entry["number"]):
                        self.assertGreaterEqual(entry["contentWidth"] + 0.01, entry["requiredContentWidth"], entry)
                        self.assertGreaterEqual(entry["labelWidth"] + 0.01, entry["advance"], entry)
                        self.assertAlmostEqual(entry["inkLeft"], entry["inkRight"], delta=1, msg=entry)
                def check_style(sample, current, occupied):
                    for entry in sample["entries"]:
                        with self.subTest(workspace=entry["number"], current=current, occupied=occupied):
                            self.assertEqual(entry["selected"], entry["number"] == current)
                            expected = sample["accent"] if entry["number"] == current or entry["number"] in occupied else sample["muted"]
                            self.assertEqual(entry["textColor"], expected, entry)
                            if entry["number"] == current:
                                self.assertEqual(entry["outline"], 1, entry)
                                self.assertEqual(entry["background"], sample["raised"], entry)
                            elif not entry["hovered"] and not entry["visualFocus"]:
                                self.assertEqual(entry["outline"], 0, entry)
                                self.assertEqual(entry["background"], "#00000000", entry)
                check_style(sample, 1, [11])
                for current, windows, occupied in [(1, 0, []), (11, 0, []), (1, 3, [11])]:
                    changed = subprocess.run([QS, "ipc", "--pid", str(process.pid), "call", "test", "sample", str(current), str(windows)],
                                             env=env, text=True, capture_output=True, timeout=5)
                    self.assertEqual(changed.returncode, 0)
                    response = subprocess.run([QS, "ipc", "--pid", str(process.pid), "call", "test", "status"],
                                              env=env, text=True, capture_output=True, timeout=5)
                    check_style(json.loads(response.stdout), current, occupied)
            finally:
                process.terminate()
                process.wait(timeout=10)
                log.seek(0)
                output = log.read()
                for problem in ["ERROR", "ReferenceError", "TypeError", "Unable to assign", "Binding loop"]:
                    self.assertNotIn(problem, output, output)

    def test_right_controls_are_compact_content_sized_and_network_is_icon_only(self):
        env = dict(os.environ, QT_QPA_PLATFORM="wayland")
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode="w+") as log:
            config = Path(directory) / "atelier"
            shutil.copytree(CONFIG, config)
            shutil.copyfile(ROOT / "tests/atelier-bar-controls.qml", config / "controls-test.qml")
            process = subprocess.Popen([QS, "-p", str(config / "controls-test.qml"), "--no-color"],
                                       env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                def ipc(*args):
                    return subprocess.run([QS, "ipc", "--pid", str(process.pid), "call", "test", *args],
                                          env=env, text=True, capture_output=True, timeout=5)
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    response = ipc("status")
                    if process.poll() is not None or (response.returncode == 0 and json.loads(response.stdout)["viewportWidth"] > 600):
                        break
                    time.sleep(0.05)
                self.assertIsNone(process.poll())
                initial = json.loads(response.stdout)
                items = initial["items"]
                self.assertEqual([item["x"] for item in items], sorted(item["x"] for item in items))
                self.assertEqual(initial["networkCaption"], "Wired")
                self.assertNotIn("Wired", items[1]["text"])
                self.assertNotIn("connection", items[1]["text"])
                self.assertIn("Wired connection 1", initial["networkHint"])
                self.assertIn("192.0.2.1", initial["networkHint"])
                for item in items:
                    self.assertAlmostEqual(item["width"], item["naturalWidth"], delta=1, msg=item)
                    self.assertEqual(item["leftPadding"], 10, item)
                    self.assertEqual(item["rightPadding"], 10, item)
                    self.assertAlmostEqual(item["contentX"], 10, delta=1, msg=item)
                    self.assertAlmostEqual(item["width"] - item["contentX"] - item["contentWidth"], 10, delta=1, msg=item)
                    self.assertAlmostEqual(item["inkLeft"], item["inkRight"], delta=1, msg=item)
                    self.assertGreaterEqual(item["labelLeft"], -0.01, item)
                    self.assertLessEqual(item["labelRight"], item["contentWidth"] + 0.01, item)
                    self.assertGreaterEqual(item["inkLeft"], item["leftPadding"] - 0.01, item)
                    self.assertGreaterEqual(item["inkRight"], item["rightPadding"] - 0.01, item)
                self.assertFalse(initial["vpn"])
                self.assertFalse(initial["bluetoothOnBar"])
                self.assertTrue(initial["bluetoothInMenu"])
                self.assertTrue(initial["castInMenu"])
                self.assertFalse(initial["castOnBar"])
                for left_index, right_index in [(0, 1), (1, 2), (2, 3), (3, 4)]:
                    gap = items[right_index]["x"] - items[left_index]["x"] - items[left_index]["width"]
                    self.assertGreaterEqual(gap, 4)
                    self.assertLessEqual(gap, 5)
                for volume, muted, vpn in [(100, False, True), (8, True, False)]:
                    self.assertEqual(ipc("sample", str(volume), str(muted).lower(), str(vpn).lower()).returncode, 0)
                    time.sleep(0.1)
                    after = json.loads(ipc("status").stdout)
                    for item in after["items"]:
                        self.assertAlmostEqual(item["width"], item["naturalWidth"], delta=1, msg=item)
                        self.assertAlmostEqual(item["inkLeft"], item["inkRight"], delta=1, msg=item)
                        self.assertGreaterEqual(item["labelLeft"], -0.01, item)
                        self.assertLessEqual(item["labelRight"], item["contentWidth"] + 0.01, item)
                    if volume == 100:
                        self.assertGreater(after["items"][0]["width"], items[0]["width"])
                    self.assertEqual(after["items"][-1]["x"], items[-1]["x"])
                    self.assertEqual(after["items"][1]["text"] != items[1]["text"], vpn)
                    self.assertEqual(after["vpn"], vpn)
                    if muted:
                        self.assertIn("Muted", after["items"][0]["text"])
                icons = {}
                for kind in ["wifi", "offline", "ethernet"]:
                    self.assertEqual(ipc("transport", kind).returncode, 0)
                    icons[kind] = json.loads(ipc("status").stdout)["items"][1]["text"]
                self.assertEqual(len(set(icons.values())), 3)
                self.assertEqual(icons["ethernet"], items[1]["text"])
                for count, dnd, icon in [(0, False, "\U000f009c"), (2, False, "\U000f009a"),
                                         (0, False, "\U000f009c"), (0, True, "\U000f009b"),
                                         (3, True, "\U000f009b"), (0, False, "\U000f009c")]:
                    self.assertEqual(ipc("notifications", str(count), str(dnd).lower()).returncode, 0)
                    entry = next(item for item in json.loads(ipc("status").stdout)["items"]
                                 if item["name"] == "notifications-control")
                    self.assertEqual(entry["text"], icon, (count, dnd, entry))
                    self.assertEqual(entry["selected"], dnd or count > 0)
                self.assertEqual(ipc("invokeMenu", "bluetooth-action").returncode, 0)
                self.assertEqual(json.loads(ipc("status").stdout)["panel"], "bluetooth")
                for name, action, target in [("cast-action", "open", "cast"), ("proton-vpn-action", "vpn", "")]:
                    self.assertEqual(ipc("invokeMenu", name).returncode, 0)
                    state = json.loads(ipc("status").stdout)
                    self.assertEqual((state["lastAction"], state["lastTarget"]), (action, target))
                    self.assertEqual(state["panel"], "", name)
            finally:
                process.terminate()
                process.wait(timeout=10)
                log.seek(0)
                output = log.read()
                for problem in ["ERROR", "ReferenceError", "TypeError", "Unable to assign", "Binding loop", "Required property"]:
                    self.assertNotIn(problem, output, output)

    def test_tooltip_is_below_button_and_does_not_follow_pointer(self):
        cursor = json.loads(subprocess.check_output(["hyprctl", "-j", "cursorpos"]))
        def warp(x, y):
            result = subprocess.run(["hyprctl", "dispatch", f"hl.dsp.cursor.move({{ x = {int(x)}, y = {int(y)} }})"],
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.strip(), "ok")
        env = dict(os.environ, QT_QPA_PLATFORM="wayland")
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode="w+") as log:
            config = Path(directory) / "atelier"
            shutil.copytree(CONFIG, config)
            shutil.copyfile(ROOT / "tests/atelier-tooltip.qml", config / "tooltip-test.qml")
            process = subprocess.Popen([QS, "-p", str(config / "tooltip-test.qml"), "--no-color"],
                                       env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                def status():
                    result = subprocess.run([QS, "ipc", "--pid", str(process.pid), "call", "test", "status"],
                                            env=env, text=True, capture_output=True, timeout=5)
                    return json.loads(result.stdout) if result.returncode == 0 else None
                deadline = time.monotonic() + 10
                state = None
                while time.monotonic() < deadline:
                    state = status()
                    if state or process.poll() is not None:
                        break
                    time.sleep(0.05)
                self.assertIsNotNone(state)
                button = state["button"]
                warp(button["x"] + 20, button["y"] + 17)
                time.sleep(0.8)
                state = status()
                self.assertTrue(state["hovered"], state)
                self.assertTrue(state["shown"], state)
                first = state["tooltip"]
                self.assertGreaterEqual(first["y"], button["y"] + button["height"] + 6, state)
                warp(button["x"] + 150, button["y"] + 17)
                time.sleep(0.15)
                self.assertEqual(status()["tooltip"], first)
            finally:
                process.terminate()
                process.wait(timeout=10)
                warp(cursor["x"], cursor["y"])
                log.seek(0)
                output = log.read()
                for problem in ["ERROR", "ReferenceError", "TypeError", "Unable to assign", "Binding loop"]:
                    self.assertNotIn(problem, output, output)

    def test_all_panels_load_and_close_without_qml_errors(self):
        env = dict(os.environ, ATELIER_PREVIEW="1", QT_QPA_PLATFORM="wayland")
        with tempfile.TemporaryFile(mode="w+") as log:
            process = subprocess.Popen([QS, "-p", str(CONFIG), "--no-color"], env=env,
                                       stdout=log, stderr=subprocess.STDOUT)
            try:
                def ipc(*args):
                    return subprocess.run([QS, "ipc", "--pid", str(process.pid), "call", "shell", *args],
                                          env=env, capture_output=True, text=True, timeout=5)
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        break
                    if ipc("health").stdout.strip() == "ready":
                        break
                    time.sleep(0.1)
                self.assertIsNone(process.poll(), "QML did not load")
                self.assertEqual(ipc("health").stdout.strip(), "ready")
                for name in ["launcher", "bindings", "audio", "audioDevices", "bluetooth", "media", "tray", "calendar", "network", "notifications", "power", "clipboard"]:
                    with self.subTest(panel=name):
                        self.assertEqual(ipc("toggle", name).returncode, 0)
                        time.sleep(0.4)
                        self.assertIn(f'"panel":"{name}"', ipc("status").stdout)
                        geometry = json.loads(ipc("status").stdout)["geometry"]
                        self.assertGreater(geometry["height"], 250)
                        self.assertGreaterEqual(geometry["y"], 40)
                        self.assertEqual(ipc("close").returncode, 0)
                self.assertIsNone(process.poll())
            finally:
                process.terminate()
                process.wait(timeout=10)
                log.seek(0)
                output = log.read()
                self.assertNotIn("ERROR", output, output)
                for problem in ["ReferenceError", "TypeError", "Unable to assign", "Binding loop", "Required property"]:
                    self.assertNotIn(problem, output, output)


if __name__ == "__main__":
    unittest.main()
