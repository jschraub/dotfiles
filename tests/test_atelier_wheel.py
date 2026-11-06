"""Real Qt wheel events on production widgets, with a fake audio backend.

ATELIER_GUI_TESTS=1 python -B -m unittest discover -s tests -p test_atelier_wheel.py -v
No real volume, pointer position, or audio settings are changed.
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
CONFIG = ROOT / "quickshell/.config/quickshell/atelier"
QS = os.environ.get("ATELIER_QS_BINARY", shutil.which("qs") or "qs")


@unittest.skipUnless(os.environ.get("ATELIER_GUI_TESTS") == "1", "opt-in: temporary audio wheel test panel")
class VolumeWheelTest(unittest.TestCase):
    def test_bar_and_slider_scroll_in_five_percent_steps_without_lost_events(self):
        env = dict(os.environ, QT_QPA_PLATFORM="wayland")
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode="w+") as log:
            config = Path(directory) / "atelier"
            shutil.copytree(CONFIG, config)
            shutil.copyfile(ROOT / "tests/atelier-volume-wheel.qml", config / "wheel-test.qml")
            process = subprocess.Popen([QS, "-p", str(config / "wheel-test.qml"), "--no-color"],
                                       env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                def ipc(*args):
                    result = subprocess.run([QS, "ipc", "--pid", str(process.pid), "call", "test", *args],
                                            env=env, capture_output=True, text=True, timeout=5)
                    return result
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    response = ipc("status")
                    if process.poll() is not None or (response.returncode == 0 and json.loads(response.stdout)["width"] > 600):
                        break
                    time.sleep(0.05)
                self.assertIsNone(process.poll())
                geometry = json.loads(ipc("status").stdout)["slider"]
                self.assertGreaterEqual(geometry["height"], 28)
                self.assertEqual(geometry["areaHeight"], geometry["height"])
                self.assertEqual(ipc("wheel", "probe", "120", "1").stdout.strip(), "true")
                self.assertEqual(json.loads(ipc("status").stdout)["rawWheels"], 1, "Qt must deliver the synthetic wheel event")
                for source in ["slider", "bar"]:
                    for start, delta, count, expected in [(50, 120, 1, 55), (50, -120, 1, 45),
                                                         (50, 120, 3, 65), (50, -120, 3, 35),
                                                         (98, 120, 2, 100), (2, -120, 2, 0),
                                                         (50, 60, 1, 50), (50, 60, 2, 55),
                                                         (50, 240, 1, 60), (50, -240, 1, 40)]:
                        with self.subTest(source=source, start=start, delta=delta, count=count):
                            self.assertEqual(ipc("reset", str(start)).returncode, 0)
                            self.assertEqual(ipc("wheel", source, str(delta), str(count)).stdout.strip(), "true")
                            time.sleep(0.12)
                            state = json.loads(ipc("status").stdout)
                            self.assertEqual(state["volume"], expected, state)
                            self.assertEqual(state["rotation"], 0, state)
                    self.assertEqual(ipc("reset", "50").returncode, 0)
                    self.assertEqual(ipc("pixels", source, "20", "2").returncode, 0)
                    self.assertEqual(json.loads(ipc("status").stdout)["volume"], 55)
                self.assertEqual(ipc("reset", "50").returncode, 0)
                self.assertEqual(ipc("clickAudio").stdout.strip(), "true")
                self.assertEqual(json.loads(ipc("status").stdout)["panel"], "audio")
                self.assertEqual(ipc("dragSlider").stdout.strip(), "true")
                time.sleep(0.15)
                dragged = json.loads(ipc("status").stdout)
                self.assertGreaterEqual(dragged["volume"], 75, dragged)
                self.assertLessEqual(dragged["volume"], 85, dragged)
            finally:
                process.terminate()
                process.wait(timeout=10)
                log.seek(0)
                output = log.read()
                for problem in ["ERROR", "ReferenceError", "TypeError", "Unable to assign", "Binding loop"]:
                    self.assertNotIn(problem, output, output)


if __name__ == "__main__":
    unittest.main()
