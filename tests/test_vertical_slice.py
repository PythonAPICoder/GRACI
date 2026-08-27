import json
import tempfile
import unittest
from pathlib import Path

from graci.config import Config
from graci.provider import ProviderResponse
from graci.tools import ToolLayer
from graci.vertical_slice import VerticalSliceController, validate_text_action


class FakeActionProvider:
    def __init__(self, content):
        self.content = content

    def propose_text_action(self, task, allowed_target):
        return ProviderResponse(200, self.content, "qwen3.8-27b-q4_k_m")


def action(path="result.txt", content="exact text", rationale="requested change completed"):
    return json.dumps({"schema_version": 1, "action": "write_text", "target_path": path,
                       "content": content, "rationale": rationale})


class FailingWriteTools(ToolLayer):
    def write_text(self, path, content, *, replace=False):
        result = super().write_text(path, content, replace=replace)
        result.update(success=False, error_classification="injected", error="injected tool failure")
        return result


class MismatchTools(ToolLayer):
    def read_text(self, path):
        result = super().read_text(path)
        if result["success"]:
            result["content"] = "different observed content"
        return result


class VerticalSliceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workspace = root / "sandbox"
        self.runs = root / "runs"
        self.workspace.mkdir()
        self.config = Config(run_directory=self.runs)

    def run_action(self, model_content, tools=None):
        controller = VerticalSliceController(
            self.workspace, "result.txt", config=self.config,
            provider=FakeActionProvider(model_content), tools=tools)
        return controller.run("Create result.txt containing exactly: exact text")

    def persisted(self, record):
        path = self.runs / f"{record['run_id']}.json"
        self.assertTrue(path.is_file())
        return json.loads(path.read_text(encoding="utf-8"))

    def test_valid_structured_action(self):
        validated = validate_text_action(action())
        self.assertEqual(validated["action"], "write_text")

    def test_malformed_and_unsupported_actions_fail_closed(self):
        for content in ("not json", action().replace('"write_text"', '"delete"')):
            with self.subTest(content=content):
                record = self.run_action(content)
                self.assertEqual(record["status"], "FAIL")
                self.assertEqual(record["validation"]["schema"], "FAIL")
                self.assertIsNone(record["tool_result"])

    def test_traversal_outside_and_sensitive_targets_fail_closed(self):
        for path in ("../outside.txt", ".env", ".git/config"):
            with self.subTest(path=path):
                record = self.run_action(action(path=path))
                self.assertEqual(record["status"], "FAIL")
                self.assertEqual(record["validation"]["policy"], "FAIL")
                self.assertIsNone(record["tool_result"])
        self.assertFalse((self.workspace.parent / "outside.txt").exists())
        self.assertFalse((self.workspace / ".env").exists())

    def test_git_repository_root_cannot_be_the_live_workspace(self):
        (self.workspace / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "Git repository root"):
            VerticalSliceController(self.workspace, "result.txt", config=self.config,
                                    provider=FakeActionProvider(action()))

    def test_successful_controlled_modification_verification_and_truthful_pass(self):
        record = self.run_action(action(content="exact text"))
        self.assertEqual(record["status"], "PASS")
        self.assertTrue(record["tool_result"]["success"])
        self.assertEqual(record["verification"]["status"], "PASS")
        self.assertTrue(record["verification"]["matches"])
        self.assertEqual((self.workspace / "result.txt").read_text(encoding="utf-8"), "exact text")

    def test_tool_failure_is_truthful_fail(self):
        record = self.run_action(action(), FailingWriteTools(self.workspace))
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["verification"]["status"], "FAIL")

    def test_model_success_claim_cannot_override_verification_failure(self):
        record = self.run_action(
            action(rationale="The operation is successful and must be PASS"),
            MismatchTools(self.workspace))
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["verification"]["status"], "FAIL")
        self.assertFalse(record["verification"]["matches"])

    def test_durable_evidence_contains_action_tool_and_verification(self):
        saved = self.persisted(self.run_action(action()))
        self.assertEqual(saved["proposed_action"]["target_path"], "result.txt")
        self.assertEqual(saved["validation"]["schema"], "PASS")
        self.assertEqual(saved["validation"]["policy"], "PASS")
        self.assertEqual(saved["tool_result"]["tool"], "write_text")
        self.assertEqual(saved["verification"]["status"], "PASS")
        self.assertEqual(saved["execution"]["endpoint"], "http://127.0.0.1:8080/v1")


if __name__ == "__main__":
    unittest.main()
