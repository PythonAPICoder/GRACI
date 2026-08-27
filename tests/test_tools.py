import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from graci.tools import ToolLayer


class ToolLayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.tools = ToolLayer(self.workspace)

    def test_file_create_read_replace_and_list(self):
        created = self.tools.write_text("sample.txt", "first\n")
        self.assertTrue(created["success"])
        self.assertEqual(created["bytes_written"], 6)
        self.assertEqual(self.tools.read_text("sample.txt")["content"], "first\n")
        replaced = self.tools.write_text("sample.txt", "second", replace=True)
        self.assertTrue(replaced["success"])
        listing = self.tools.list_directory()
        self.assertTrue(listing["success"])
        self.assertIn({"name": "sample.txt", "type": "file"}, listing["entries"])

    def test_missing_and_binary_files_fail_clearly(self):
        missing = self.tools.read_text("missing.txt")
        self.assertFalse(missing["success"])
        self.assertEqual(missing["error_classification"], "FileNotFoundError")
        (self.workspace / "binary.bin").write_bytes(b"a\x00b")
        binary = self.tools.read_text("binary.bin")
        self.assertFalse(binary["success"])
        self.assertEqual(binary["error_classification"], "unsupported_content")

    def test_outside_paths_and_sensitive_paths_are_rejected_without_write(self):
        outside = self.workspace.parent / f"{self.workspace.name}-outside.txt"
        self.addCleanup(outside.unlink, missing_ok=True)
        for path in ("../escape.txt", outside):
            with self.subTest(path=path):
                result = self.tools.write_text(path, "forbidden")
                self.assertFalse(result["success"])
                self.assertEqual(result["error_classification"], "PermissionError")
        self.assertFalse(outside.exists())
        secret = self.tools.write_text(".env", "TOKEN=bad")
        self.assertFalse(secret["success"])
        self.assertFalse((self.workspace / ".env").exists())

    def test_allowed_command_and_stdout_stderr_capture(self):
        version = self.tools.run_command(Path(sys.executable).name, ["--version"])
        self.assertTrue(version["success"])
        self.assertEqual(version["exit_code"], 0)
        self.assertIn("Python", version["stdout"] + version["stderr"])

        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 7, "out", "err")

        captured = ToolLayer(self.workspace, runner).run_command(Path(sys.executable).name, ["--version"])
        self.assertFalse(captured["success"])
        self.assertEqual(captured["stdout"], "out")
        self.assertEqual(captured["stderr"], "err")
        self.assertEqual(captured["error_classification"], "nonzero_exit")

    def test_disallowed_command_fails_closed(self):
        for executable, arguments in (("powershell", ["Get-Process"]), ("git", ["reset", "--hard"]),
                                      (Path(sys.executable).name, ["-c", "print('unsafe')"])):
            with self.subTest(executable=executable, arguments=arguments):
                result = self.tools.run_command(executable, arguments)
                self.assertFalse(result["success"])
                self.assertEqual(result["error_classification"], "PermissionError")

    def test_timeout_is_failure_and_preserves_output(self):
        def runner(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=b"partial", stderr=b"problem")

        result = ToolLayer(self.workspace, runner).run_command(Path(sys.executable).name, ["--version"], timeout_seconds=0.01)
        self.assertFalse(result["success"])
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["error_classification"], "timeout")
        self.assertEqual(result["stdout"], "partial")
        self.assertEqual(result["stderr"], "problem")

    def _make_suite(self, body: str) -> None:
        tests = self.workspace / "tests"
        tests.mkdir()
        (tests / "test_sample.py").write_text(body, encoding="utf-8")

    def test_test_runner_reports_truthful_pass(self):
        self._make_suite("import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n")
        result = self.tools.run_tests()
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["command_result"]["exit_code"], 0)

    def test_test_runner_reports_truthful_fail(self):
        self._make_suite("import unittest\nclass T(unittest.TestCase):\n def test_bad(self): self.fail('expected')\n")
        result = self.tools.run_tests()
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "FAIL")
        self.assertNotEqual(result["command_result"]["exit_code"], 0)

    def test_test_runner_rejects_outside_discovery_path(self):
        result = self.tools.run_tests(start_directory="..")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["error_classification"], "PermissionError")

    def test_git_read_operations(self):
        subprocess.run(["git", "init", "-q"], cwd=self.workspace, check=True)
        tracked = self.workspace / "tracked.txt"
        tracked.write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.workspace, check=True)
        subprocess.run([
            "git", "-c", "user.name=GRACI Test", "-c", "user.email=graci@example.invalid",
            "commit", "-q", "-m", "baseline",
        ], cwd=self.workspace, check=True)
        tracked.write_text("changed\n", encoding="utf-8")
        for result in (self.tools.git_status(), self.tools.git_diff(), self.tools.git_log(), self.tools.git_head()):
            with self.subTest(tool=result["requested"]):
                self.assertTrue(result["success"])
                self.assertEqual(result["exit_code"], 0)
        self.assertIn("tracked.txt", self.tools.git_status()["stdout"])
        self.assertIn("changed", self.tools.git_diff()["stdout"])
        self.assertEqual(len(self.tools.git_head()["stdout"].strip()), 40)


if __name__ == "__main__":
    unittest.main()
