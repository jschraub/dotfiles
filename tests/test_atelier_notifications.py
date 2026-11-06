"""Real notification protocol on a PRIVATE bus. Never takes over SwayNC.

ATELIER_NOTIFICATION_TESTS=1 python -B -m unittest discover -s tests -p test_atelier_notifications.py
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
QS = os.environ.get("ATELIER_QS_BINARY", shutil.which("qs") or "qs")


@unittest.skipUnless(os.environ.get("ATELIER_NOTIFICATION_TESTS") == "1", "opt-in: private DBus notification integration")
class NotificationTest(unittest.TestCase):
    def test_replacement_expiration_dnd_actions_and_clear(self):
        bus = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"],
                               stdout=subprocess.PIPE, text=True)
        env = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=bus.stdout.readline().strip(),
                   QT_QPA_PLATFORM="wayland", QT_NO_XDG_DESKTOP_PORTAL="1")
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode="w+") as log:
            config = Path(directory) / "atelier"
            shutil.copytree(ROOT / "quickshell/.config/quickshell/atelier", config)
            shutil.copyfile(ROOT / "tests/atelier-notifications.qml", config / "harness.qml")
            process = subprocess.Popen([QS, "-p", str(config / "harness.qml"), "--no-color"],
                                       env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                def ipc(*args):
                    return subprocess.run([QS, "ipc", "--pid", str(process.pid), "call", "test", *args],
                                          env=env, capture_output=True, text=True, timeout=5)
                def status():
                    return json.loads(ipc("status").stdout)
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if process.poll() is not None or ipc("status").returncode == 0:
                        break
                    time.sleep(0.1)
                self.assertIsNone(process.poll())
                information = subprocess.check_output([
                    "gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                    "--object-path", "/org/freedesktop/Notifications", "--method",
                    "org.freedesktop.Notifications.GetServerInformation",
                ], env=env, text=True, timeout=5)
                self.assertIn("quickshell", information.lower())
                def notify(title, replacement=0, timeout=10000, actions="[]", hints="{}"):
                    result = subprocess.run([
                        "gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                        "--object-path", "/org/freedesktop/Notifications", "--method",
                        "org.freedesktop.Notifications.Notify", "Atelier test", str(replacement),
                        "", title, "A <literal> body", actions, hints, str(timeout),
                    ], env=env, text=True, capture_output=True, check=True, timeout=5)
                    return int(result.stdout.split("uint32 ")[1].split(",")[0])
                first = notify("Original")
                self.assertEqual(status()["live"], 1)
                replacement = notify("Updated", replacement=first, timeout=200)
                self.assertEqual(first, replacement)
                self.assertEqual(status()["count"], 1)
                self.assertEqual(status()["titles"], ["Updated"])
                time.sleep(0.6)
                self.assertEqual(status()["live"], 0, status())
                self.assertEqual(status()["count"], 1)  # expired history retained
                ipc("dnd", "true")
                notify("Quiet", timeout=0)
                self.assertEqual(status()["toasts"], 0)
                self.assertEqual(status()["count"], 2)
                notify("Action", actions="['default', 'Open']")
                ipc("invoke")
                self.assertEqual(status()["live"], 1)  # only Quiet remains live
                notify("Transient", timeout=100, hints="{'transient': <true>}")
                time.sleep(0.5)
                self.assertNotIn("Transient", status()["titles"])
                notify("Critical", timeout=100, hints="{'urgency': <byte 2>}")
                time.sleep(0.5)
                self.assertEqual(status()["toasts"], 1)  # critical bypasses DND and never auto-expires
                ipc("clear")
                self.assertEqual(status()["count"], 0)
            finally:
                process.terminate()
                process.wait(timeout=10)
                bus.terminate()
                bus.wait(timeout=5)
                bus.stdout.close()
                log.seek(0)
                output = log.read()
                for problem in ["ERROR", "ReferenceError", "TypeError", "Unable to assign", "Binding loop", "Required property"]:
                    self.assertNotIn(problem, output, output)


if __name__ == "__main__":
    unittest.main()
