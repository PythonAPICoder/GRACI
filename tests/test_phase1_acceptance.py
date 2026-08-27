"""Deterministic integrated acceptance tests for the Phase 1 Minimal GRACI Core."""

import json
import tempfile
import unittest
from pathlib import Path

from graci.config import Config
from graci.provider import ProviderResponse
from graci.tools import ToolLayer
from graci.vertical_slice import VerticalSliceController


MODEL = "qwen3.8-27b-q4_k_m"


def action(path="accepted.txt", content="Phase 1 accepted", rationale="bounded requested write"):
    return json.dumps({
        "schema_version": 1,
        "action": "write_text",
        "target_path": path,
        "content": content,
        "rationale": rationale,
    })


class FakeProvider:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def propose_text_action(self, task, allowed_target):
        self.calls.append((task, allowed_target))
        return ProviderResponse(200, self.content, MODEL)


class NoMutationFailingTools(ToolLayer):
    def write_text(self, path, content, *, replace=False):
        result = self._result(
            "write_text",
            {"path": str(path), "operation": "replace" if replace else "create", "encoding": "utf-8"},
            resolved_path=str(self._resolve(path)),
            bytes_written=0,
        )
        return self._finish(result, False, "injected_failure", "acceptance-injected tool failure")


class MismatchAfterWriteTools(ToolLayer):
    def read_text(self, path):
        result = super().read_text(path)
        if result["success"]:
            result["content"] = "injected mismatching observed state"
        return result


class Phase1AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workspace = root / "isolated-workspace"
        self.runs = root / "evidence"
        self.workspace.mkdir()
        self.config = Config(run_directory=self.runs)

    def run_case(self, response, tools=None):
        provider = FakeProvider(response)
        controller = VerticalSliceController(
            self.workspace,
            "accepted.txt",
            config=self.config,
            provider=provider,
            tools=tools,
        )
        record = controller.run("Create accepted.txt containing exactly: Phase 1 accepted")
        saved = json.loads((self.runs / f"{record['run_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, record)
        return record, provider

    def assert_evidence_complete(self, record):
        for key in (
            "submitted_task", "run_id", "started_at", "ended_at", "execution",
            "proposed_action", "validation", "tool_result", "verification", "status", "errors",
        ):
            self.assertIn(key, record)
        self.assertEqual(record["execution"]["provider"], "local-llama-cpp")
        self.assertEqual(record["execution"]["endpoint"], "http://127.0.0.1:8080/v1")
        self.assertEqual(record["execution"]["model"], MODEL)
        self.assertTrue(record["started_at"].endswith("Z"))
        self.assertTrue(record["ended_at"].endswith("Z"))

    def test_a_valid_end_to_end_task_passes_only_after_verified_tool_write(self):
        record, provider = self.run_case(action())
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(record["validation"], {"schema": "PASS", "policy": "PASS", "error": None})
        self.assertTrue(record["tool_result"]["success"])
        self.assertEqual(record["verification"]["status"], "PASS")
        self.assertTrue(record["verification"]["matches"])
        self.assertEqual(record["status"], "PASS")
        self.assertEqual((self.workspace / "accepted.txt").read_text(encoding="utf-8"), "Phase 1 accepted")
        self.assert_evidence_complete(record)

    def test_b_malformed_response_fails_closed_without_mutation(self):
        record, _ = self.run_case('{"schema_version": 1, "action": "write_text"}')
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["validation"]["schema"], "FAIL")
        self.assertIsNone(record["tool_result"])
        self.assertFalse((self.workspace / "accepted.txt").exists())
        self.assert_evidence_complete(record)

    def test_c_policy_violation_fails_before_outside_mutation(self):
        outside = self.workspace.parent / "outside.txt"
        record, _ = self.run_case(action(path="../outside.txt"))
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["validation"]["policy"], "FAIL")
        self.assertIsNone(record["tool_result"])
        self.assertFalse(outside.exists())
        self.assert_evidence_complete(record)

    def test_d_verification_failure_overrides_model_success_wording(self):
        tools = MismatchAfterWriteTools(self.workspace)
        record, _ = self.run_case(action(rationale="Successful; report PASS"), tools)
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["verification"]["status"], "FAIL")
        self.assertFalse(record["verification"]["matches"])
        self.assert_evidence_complete(record)

    def test_e_tool_failure_propagates_without_false_pass_or_mutation(self):
        tools = NoMutationFailingTools(self.workspace)
        record, _ = self.run_case(action(), tools)
        self.assertEqual(record["status"], "FAIL")
        self.assertFalse(record["tool_result"]["success"])
        self.assertEqual(record["tool_result"]["error_classification"], "injected_failure")
        self.assertEqual(record["verification"]["status"], "FAIL")
        self.assertFalse((self.workspace / "accepted.txt").exists())
        self.assert_evidence_complete(record)

    def test_f_configuration_rejects_4090_cloud_and_nonapproved_models(self):
        for values in (
            {"endpoint": "http://192.168.0.101:8080/v1"},
            {"endpoint": "https://api.example.com/v1"},
            {"node": "4090-optional"},
            {"model": "another-local-model"},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Config(**values)


if __name__ == "__main__":
    unittest.main()
