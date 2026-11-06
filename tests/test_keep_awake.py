"""Keep-awake status tests plus opt-in live integration tests.

Run normally: python -m unittest discover -s tests -p test_keep_awake.py -v.
Live: DOTFILES_LIVE_TESTS=1 python -m unittest discover -s tests -p test_keep_awake.py -v.
The live tests require Linux, jq, systemd/logind and a running user manager. Add only a
temporary idle inhibitor; never suspends, reloads Waybar, or changes the user's
real keep-awake toggle. A disposable process stands in for the compositor.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid


SCRIPT = Path(__file__).resolve().parents[1] / "waybar/.local/bin/keep-awake.sh"


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


@unittest.skipUnless(shutil.which('jq'), 'jq is required for the status formatter')
class KeepAwakeStatusTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.response = self.root / 'response.json'
        binary = self.root / 'systemd-inhibit'
        binary.write_text('#!/bin/sh\ncat "$INHIBITOR_RESPONSE"\nexit "${INHIBITOR_EXIT:-0}"\n')
        binary.chmod(0o755)

    def status(self, response, code=0):
        self.response.write_text(response)
        result = subprocess.run([str(SCRIPT), 'status'], check=True, text=True,
                                capture_output=True, env=dict(
                                    os.environ, PATH=f'{self.root}:{os.environ["PATH"]}',
                                    INHIBITOR_RESPONSE=str(self.response), INHIBITOR_EXIT=str(code)))
        return json.loads(result.stdout)

    def test_status_matches_own_idle_blocker_only(self):
        own = dict(who='dotfiles-keep-awake', uid=os.getuid(), what='idle', mode='block')
        self.assertEqual(self.status(json.dumps([own]))['class'], 'activated')
        self.assertEqual(self.status(json.dumps([own]))['text'], '󰅶')
        self.assertEqual(self.status('[]')['class'], 'deactivated')
        self.assertEqual(self.status('[]')['text'], '󰛊')
        for change in [dict(uid=os.getuid() + 1), dict(who='other'),
                       dict(what='sleep'), dict(mode='delay')]:
            with self.subTest(change=change):
                self.assertEqual(self.status(json.dumps([own | change]))['class'], 'deactivated')

    def test_query_failure_or_malformed_response_shows_error(self):
        self.assertEqual(self.status('[]', 1)['class'], 'error')
        for response in ['', 'not json', '{}', 'null', '[1]', '[]\n[]']:
            with self.subTest(response=response):
                self.assertEqual(self.status(response)['class'], 'error')


@unittest.skipUnless(os.environ.get('DOTFILES_LIVE_TESTS') == '1',
                     'set DOTFILES_LIVE_TESTS=1 to exercise the real user manager/logind')
class KeepAwakeLiveTest(unittest.TestCase):
    def test_inhibitor_outlives_launcher_but_not_session(self):
        name = "dotfiles-keep-awake-test-" + uuid.uuid4().hex
        watched = subprocess.Popen(["sleep", "60"])
        try:
            stat = Path(f"/proc/{watched.pid}/stat").read_text()
            birth = stat.rsplit(") ", 1)[1].split()[19]
            # The launcher returns immediately, just as a Waybar click handler
            # does. The user manager, not that caller, must own the inhibitor.
            run("systemd-run", "--user", "--quiet", "--collect",
                "--service-type=exec", f"--unit={name}",
                "/usr/bin/systemd-inhibit", "--no-ask-password", "--what=idle",
                "--mode=block", f"--who={name}", "--why=keep-awake regression test",
                str(SCRIPT), "hold", str(watched.pid), birth)

            def inhibitors():
                return [i for i in json.loads(run(
                    "systemd-inhibit", "--list", "--json=short", "--no-pager"))
                    if i["who"] == name]

            deadline = time.monotonic() + 5
            while not inhibitors() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertTrue(inhibitors(), "No inhibitor after launcher exited")
            self.assertEqual(inhibitors()[0]["what"], "idle")
            self.assertEqual(inhibitors()[0]["mode"], "block")
            time.sleep(0.3)
            self.assertTrue(inhibitors(), "Inhibitor depended on caller lifetime")

            watched.terminate()
            watched.wait(timeout=3)
            deadline = time.monotonic() + 5
            while inhibitors() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertFalse(inhibitors(), "Inhibitor survived session exit")
        finally:
            if watched.poll() is None:
                watched.terminate()
                watched.wait(timeout=3)
            subprocess.run(["systemctl", "--user", "stop", name],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_status_reports_real_logind_state(self):
        status = json.loads(run(str(SCRIPT), "status"))
        active = any(i["who"] == "dotfiles-keep-awake" and
                     i["uid"] == os.getuid() and i["what"] == "idle" and
                     i["mode"] == "block"
                     for i in json.loads(run("systemd-inhibit", "--list",
                                             "--json=short", "--no-pager")))
        self.assertEqual(status["class"], "activated" if active else "deactivated")


if __name__ == "__main__":
    unittest.main()
