"""Exercise the real gate with fake pacman and no root or package changes."""

import pathlib
import subprocess
import tempfile
import unittest


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "usr/local/libexec/upall-pacman"


class PacmanGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="upall-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = pathlib.Path(self.temporary.name)
        self.cache = self.directory / "cache"
        self.cache.mkdir()
        self.package = self.cache / "example-1-1-any.pkg.tar.zst"
        self.package.touch()
        self.arguments = self.directory / "arguments"
        pacman = self.directory / "pacman"
        pacman.write_text(f'#!/bin/bash\nprintf "%s\\0" "$@" > "{self.arguments}"\n')
        pacman.chmod(0o700)

        # Exercise privileged validation as a normal user. Only redirect the
        # executable/cache and bypass the unprivileged query passthrough.
        source = SOURCE.read_text()
        source = source.replace("PACMAN=/usr/bin/pacman", f'PACMAN="{pacman}"')
        source = source.replace("PARU_CACHE=/home/jars/.cache/paru/clone", f'PARU_CACHE="{self.cache}"')
        source = source.replace("if ((EUID != 0)); then", "if false; then")
        self.gate = self.directory / "gate"
        self.gate.write_text(source)

    def invoke(self, *arguments):
        return subprocess.run(
            ["bash", str(self.gate), *map(str, arguments)],
            capture_output=True,
            text=True,
        )

    def assert_allowed(self, *arguments):
        result = self.invoke(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        forwarded = self.arguments.read_bytes().split(b"\0")[:-1]
        self.assertEqual(forwarded, [str(arg).encode() for arg in arguments])

    def assert_denied(self, *arguments):
        self.arguments.unlink(missing_ok=True)
        result = self.invoke(*arguments)
        self.assertEqual(result.returncode, 64, result.stderr)
        self.assertIn("refused an unsupported pacman invocation", result.stderr)
        self.assertFalse(self.arguments.exists(), "Rejected commands must never reach pacman")

    def test_paru_archive_install_with_repeated_noconfirm(self):
        # Captured from Paru at its sudo boundary when installing VS Code.
        self.assert_allowed("--upgrade", "--noconfirm", "--noconfirm", "--", self.package)

    def test_repository_upgrade_with_repeated_noconfirm(self):
        self.assert_allowed("--sync", "-y", "-u", "--noconfirm", "--noconfirm")

    def test_existing_allowed_operations(self):
        self.assert_allowed("--sync", "-y", "-u", "--noconfirm")
        self.assert_allowed("--sync", "--asdeps", "--needed", "--noconfirm", "example")
        self.assert_allowed("--upgrade", "--needed", "--noconfirm", "--ask=4", self.package)

    def test_rejects_unsafe_operations_and_options(self):
        for arguments in (
            ("--remove", "--noconfirm", "example"),
            ("--sync", "--noconfirm", "example"),
            ("--sync", "-y", "-y", "-u", "--noconfirm"),
            ("--upgrade", self.package),
            ("--upgrade", "--noconfirm"),
            ("--upgrade", "--noconfirm", "--overwrite=*", self.package),
            ("--upgrade", "--noconfirm", "--ask=1", self.package),
            ("--upgrade", "--noconfirm", "--ask=4", "--ask=4", self.package),
            ("--upgrade", "--noconfirm", "--config", "/tmp/pacman.conf", self.package),
        ):
            with self.subTest(arguments=arguments):
                self.assert_denied(*arguments)

    def test_rejects_packages_outside_cache_and_symlink_escapes(self):
        outside = self.directory / "outside.pkg.tar.zst"
        outside.touch()
        symlink = self.cache / "escape.pkg.tar.zst"
        symlink.symlink_to(outside)
        for package in (outside, symlink, self.cache / "missing.pkg.tar.zst"):
            with self.subTest(package=package):
                self.assert_denied("--upgrade", "--noconfirm", package)


if __name__ == "__main__":
    unittest.main()
