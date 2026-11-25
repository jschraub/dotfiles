"""Test custom updater dispatch without updating real software."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

FISH = shutil.which("fish")
EXAMPLE = Path(__file__).resolve().parents[1] / "examples/upall-custom.fish"
SCRIPT = Path(os.environ.get("UPALL_CUSTOM_TEST_SCRIPT", str(EXAMPLE)))


@unittest.skipUnless(FISH, "Fish is required")
class CustomUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="custom-updater-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home with spaces"
        self.home.mkdir()
        self.root = self.home / "Games/AsheronsCall"
        self.checkout = self.home / "code/ac-jars"
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        pgrep = bin_dir / "pgrep"
        pgrep.write_text('#!/bin/sh\n[ "$1" = "-x" ] && [ "$2" = ACUnreal ] || exit 2\n[ "${FIXTURE_CLIENT_RUNNING:-0}" = 1 ]\n')
        pgrep.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home),
                        PATH=str(bin_dir) + os.pathsep + os.environ["PATH"])

    def fixture(self):
        self.root.mkdir(parents=True)
        (self.root / ".ac-jars-root.json").write_text("fixture")
        self.checkout.mkdir(parents=True)
        (self.checkout / "install.sh").write_text('''#!/bin/sh
printf '%s\\n' "$@" > "$HOME/invocation"
exit "${FIXTURE_UPDATE_STATUS:-0}"
''')

    def run_script(self):
        return subprocess.run([FISH, "--no-config", str(SCRIPT)], env=self.env,
                              capture_output=True, text=True, timeout=15)

    def test_missing_client_does_not_install_anything(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not installed", result.stdout)
        self.assertFalse(self.root.exists())
        self.assertFalse((self.home / "invocation").exists())

    def test_closed_clients_run_the_requested_command(self):
        self.fixture()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / "invocation").read_text().splitlines(),
                         ["update", "--yes", "--no-shortcut"])

    def test_running_client_skips_update(self):
        self.fixture()
        self.env["FIXTURE_CLIENT_RUNNING"] = "1"
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("running; skipping", result.stdout)
        self.assertFalse((self.home / "invocation").exists())

    def test_installer_failure_is_preserved(self):
        self.fixture()
        self.env["FIXTURE_UPDATE_STATUS"] = "7"
        self.assertEqual(self.run_script().returncode, 7)

    def test_missing_installer_fails(self):
        self.root.mkdir(parents=True)
        (self.root / ".ac-jars-root.json").write_text("fixture")
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / "invocation").exists())
