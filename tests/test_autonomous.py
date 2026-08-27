"""Deterministic Phase 2A autonomous repair-loop tests."""

import json
import tempfile
import unittest
from pathlib import Path

from graci.autonomous import AutonomousRepairController, LoopLimits
from graci.config import Config
from graci.provider import ProviderError, ProviderResponse
from graci.tools import ToolLayer


MODEL = "qwen3.8-27b-q4_k_m"


def decision(action, rationale="bounded decision", **values):
    result = {"schema_version": 1, "action": action, **values, "rationale": rationale}
    return json.dumps(result)


class SequenceProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.contexts = []

    def propose_repair_decision(self, task, context):
        self.contexts.append(context)
        if not self.responses:
            raise AssertionError("provider called beyond scripted responses")
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return ProviderResponse(200, value, MODEL)


class FailingWriteTools(ToolLayer):
    def write_text(self, path, content, *, replace=False):
        result = self._result("write_text", {"path": str(path)}, bytes_written=0)
        return self._finish(result, False, "injected_failure", "injected tool failure")


class InconsistentTestTools(ToolLayer):
    def run_tests(self, *, start_directory="tests", timeout_seconds=120.0):
        result = super().run_tests(start_directory=start_directory, timeout_seconds=timeout_seconds)
        result["success"] = True
        result["status"] = "PASS"
        result["command_result"]["success"] = True
        return result


class AutonomousRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workspace = root / "fixture"
        self.runs = root / "evidence"
        (self.workspace / "tests").mkdir(parents=True)
        (self.workspace / "calculator.py").write_text(
            "def add(a, b):\n    return a - b\n", encoding="utf-8")
        (self.workspace / "tests" / "test_calculator.py").write_text(
            "import unittest\nfrom calculator import add\n\n"
            "class CalculatorTests(unittest.TestCase):\n"
            "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n",
            encoding="utf-8")
        self.config = Config(run_directory=self.runs)

    def run_loop(self, responses, *, limits=None, tools=None):
        provider = SequenceProvider(responses)
        controller = AutonomousRepairController(
            self.workspace,
            readable_files=["calculator.py", "tests/test_calculator.py"],
            editable_files=["calculator.py"], config=self.config, provider=provider,
            tools=tools, limits=limits)
        record = controller.run("Inspect this project, repair the defect, and verify tests pass.")
        saved = json.loads((self.runs / f"{record['run_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, record)
        return record, provider

    @staticmethod
    def correct_source():
        return "def add(a, b):\n    return a + b\n"

    def test_successful_direct_repair(self):
        record, provider = self.run_loop([
            decision("inspect_file", target_path="calculator.py"),
            decision("write_text", target_path="calculator.py", content=self.correct_source()),
            decision("run_tests"),
        ])
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["terminal_reason"], "tests_passed")
        self.assertEqual(record["repair_attempts"], 1)
        self.assertEqual(len(record["cycles"]), 3)
        self.assertIn("return a - b", provider.contexts[1]["recent_cycles"][-1]["tool_result"]["content"])

    def test_failed_first_repair_then_successful_repair_uses_feedback(self):
        record, provider = self.run_loop([
            decision("write_text", target_path="calculator.py",
                     content="def add(a, b):\n    return a * b\n"),
            decision("run_tests"),
            decision("write_text", target_path="calculator.py", content=self.correct_source()),
            decision("run_tests"),
        ])
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["repair_attempts"], 2)
        self.assertEqual(record["cycles"][1]["tool_result"]["status"], "FAIL")
        feedback = provider.contexts[2]["recent_cycles"][-1]["tool_result"]
        self.assertIn("AssertionError", feedback["command_result"]["stderr"])

    def test_repair_exhaustion_is_not_pass(self):
        bad = "def add(a, b):\n    return 0\n"
        record, _ = self.run_loop([
            decision("write_text", target_path="calculator.py", content=bad), decision("run_tests"),
            decision("write_text", target_path="calculator.py", content=bad), decision("run_tests"),
        ])
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["terminal_reason"], "repair_budget_exhausted")
        self.assertEqual(record["deterministic_verification"]["status"], "FAIL")

    def test_malformed_and_unsupported_decisions_fail_without_mutation(self):
        original = (self.workspace / "calculator.py").read_text(encoding="utf-8")
        policy_change = json.loads(decision("run_tests"))
        policy_change["max_repairs"] = 99
        for response in ("not json", decision("delete_file", target_path="calculator.py"),
                         json.dumps(policy_change)):
            with self.subTest(response=response):
                record, _ = self.run_loop([response])
                self.assertEqual(record["terminal_reason"], "schema_validation_failure")
                self.assertIsNone(record["cycles"][0]["tool_result"])
                self.assertEqual((self.workspace / "calculator.py").read_text(encoding="utf-8"), original)

    def test_policy_rejects_outside_and_noneditable_targets(self):
        absolute_outside = str((self.workspace.parent / "absolute-outside.py").resolve())
        for target in ("../outside.py", absolute_outside, "tests/test_calculator.py", ".git/config"):
            with self.subTest(target=target):
                record, _ = self.run_loop([
                    decision("write_text", target_path=target, content="forbidden")])
                self.assertEqual(record["terminal_reason"], "policy_violation")
                self.assertEqual(record["cycles"][0]["policy_validation"]["status"], "FAIL")
        self.assertFalse((self.workspace.parent / "outside.py").exists())
        self.assertFalse((self.workspace.parent / "absolute-outside.py").exists())

    def test_tool_failure_is_not_pass(self):
        tools = FailingWriteTools(self.workspace)
        record, _ = self.run_loop([
            decision("write_text", target_path="calculator.py", content=self.correct_source())], tools=tools)
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["terminal_reason"], "tool_failure")

    def test_model_finish_cannot_override_failed_tests(self):
        record, _ = self.run_loop([decision("run_tests"), decision("finish", rationale="tests are fine")])
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["terminal_reason"], "model_finished_without_passing_tests")

    def test_iteration_bound(self):
        record, provider = self.run_loop([
            decision("inspect_file", target_path="calculator.py"),
            decision("inspect_file", target_path="calculator.py"),
        ], limits=LoopLimits(max_iterations=2, max_repairs=1))
        self.assertEqual(len(provider.contexts), 2)
        self.assertEqual(len(record["cycles"]), 2)
        self.assertEqual(record["terminal_reason"], "iteration_budget_exhausted")

    def test_provider_failure_and_model_identity_failure(self):
        record, _ = self.run_loop([ProviderError("offline", 503)])
        self.assertEqual(record["terminal_reason"], "provider_failure")
        provider = SequenceProvider([decision("inspect_file", target_path="calculator.py")])
        provider.propose_repair_decision = lambda task, context: ProviderResponse(200, provider.responses[0], "other")
        controller = AutonomousRepairController(
            self.workspace, readable_files=["calculator.py", "tests/test_calculator.py"],
            editable_files=["calculator.py"], config=self.config, provider=provider)
        record = controller.run("repair")
        self.assertEqual(record["terminal_reason"], "schema_validation_failure")

    def test_inconsistent_test_evidence_fails_verification(self):
        tools = InconsistentTestTools(self.workspace)
        record, _ = self.run_loop([decision("run_tests")], tools=tools)
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["terminal_reason"], "deterministic_verification_failure")

    def test_evidence_records_cycles_contract_limits_and_terminal_reason(self):
        record, _ = self.run_loop([
            decision("write_text", target_path="calculator.py", content=self.correct_source()),
            decision("run_tests"),
        ])
        self.assertEqual(record["limits"]["max_repairs"], 2)
        self.assertEqual(record["policy"]["allowed_actions"],
                         ["list_files", "inspect_file", "write_text", "run_tests", "finish"])
        for cycle in record["cycles"]:
            self.assertEqual(cycle["schema_validation"]["status"], "PASS")
            self.assertEqual(cycle["policy_validation"]["status"], "PASS")
            self.assertIsNotNone(cycle["ended_at"])
        self.assertEqual(record["deterministic_verification"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
