"""Integrated deterministic acceptance for complete Phase 2 autonomy."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from graci.autonomous import AutonomousRepairController, LoopLimits
from graci.config import Config
from graci.provider import ProviderError, ProviderResponse
from graci.tools import ToolLayer

MODEL = "qwen3.8-27b-q4_k_m"


def decision(action, **values):
    return json.dumps({"schema_version": 1, "action": action, **values, "rationale": "acceptance"})


class ScriptedProvider:
    def __init__(self, responses):
        self.responses, self.contexts, self.calls = list(responses), [], 0

    def propose_repair_decision(self, task, context):
        self.calls += 1
        self.contexts.append(context)
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return ProviderResponse(200, value, MODEL)


class ExplodingTestTools(ToolLayer):
    def run_tests(self, **kwargs):
        raise OSError("injected governed test execution failure")


class Phase2CAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workspace, self.runs = root / "fixture", root / "evidence"
        (self.workspace / "tests").mkdir(parents=True)
        (self.workspace / "rules.py").write_text("OFFSET = 1\n", encoding="utf-8")
        (self.workspace / "service.py").write_text(
            "from rules import OFFSET\n\ndef score(value):\n    return value - OFFSET\n", encoding="utf-8")
        (self.workspace / "tests" / "test_service.py").write_text(
            "import unittest\nfrom service import score\n\nclass Tests(unittest.TestCase):\n"
            "    def test_score(self):\n        self.assertEqual(score(5), 7)\n", encoding="utf-8")
        self.config = Config(run_directory=self.runs)

    def run_loop(self, responses, *, limits=None, tools=None):
        provider = ScriptedProvider(responses)
        controller = AutonomousRepairController(
            self.workspace,
            readable_files=["rules.py", "service.py", "tests/test_service.py"],
            editable_files=["rules.py", "service.py"], test_directory="tests",
            config=self.config, provider=provider, tools=tools,
            limits=limits or LoopLimits(max_iterations=12, max_model_calls=12,
                max_file_inspections=6, max_file_modifications=4, max_repairs=2))
        record = controller.run("Inspect the related files, repair scoring, and prove it with tests.")
        evidence_path = self.runs / f"{record['run_id']}.json"
        self.assertEqual(record, json.loads(evidence_path.read_text(encoding="utf-8")))
        return record, provider

    def assert_truthful_failure(self, record, reason):
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["terminal_reason"], reason)
        self.assertEqual(record["deterministic_verification"]["status"], "FAIL")

    def test_direct_success_and_evidence_integrity(self):
        record, _ = self.run_loop([
            decision("inspect_file", target_path="service.py"),
            decision("write_text", target_path="service.py", content="from rules import OFFSET\n\ndef score(value):\n    return value + OFFSET + 1\n"),
            decision("run_tests")])
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["terminal_reason"], "tests_passed")
        self.assertEqual(record["deterministic_verification"]["status"], "PASS")
        self._assert_reconstructable(record)

    def test_multifile_success_requires_two_governed_modifications(self):
        record, _ = self.run_loop([
            decision("list_files"),
            decision("inspect_file", target_path="service.py"),
            decision("inspect_file", target_path="rules.py"),
            decision("inspect_file", target_path="tests/test_service.py"),
            decision("write_text", target_path="service.py", content="from rules import OFFSET\n\ndef score(value):\n    return value + OFFSET\n"),
            decision("write_text", target_path="rules.py", content="OFFSET = 2\n"),
            decision("run_tests")])
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["modified_paths"], ["service.py", "rules.py"])
        self.assertEqual(record["budget_usage"]["file_modifications"], 2)
        self.assertTrue(all(c["policy_validation"]["status"] == "PASS" for c in record["cycles"]))

    def test_failed_repair_feedback_then_success_and_post_failure_budget(self):
        record, provider = self.run_loop([
            decision("write_text", target_path="service.py", content="from rules import OFFSET\n\ndef score(value):\n    return value + OFFSET\n"),
            decision("write_text", target_path="rules.py", content="OFFSET = 1\n"),
            decision("run_tests"),
            decision("write_text", target_path="rules.py", content="OFFSET = 2\n"),
            decision("run_tests")])
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["budget_usage"]["file_modifications"], 3)
        self.assertEqual(record["budget_usage"]["repairs"], 1)
        self.assertIn("AssertionError", provider.contexts[3]["recent_cycles"][-1]["tool_result"]["command_result"]["stderr"])

    def test_hard_budgets_fail_closed_without_execution_beyond_limits(self):
        cases = [
            (LoopLimits(max_iterations=2, max_model_calls=2, max_file_inspections=2, max_file_modifications=2, max_repairs=1),
             [decision("list_files"), decision("inspect_file", target_path="service.py")], "iteration_budget_exhausted", 2),
            (LoopLimits(max_iterations=3, max_model_calls=1, max_file_inspections=2, max_file_modifications=2, max_repairs=1),
             [decision("list_files")], "model_call_budget_exhausted", 1),
            (LoopLimits(max_iterations=3, max_model_calls=3, max_file_inspections=1, max_file_modifications=2, max_repairs=1),
             [decision("inspect_file", target_path="service.py"), decision("inspect_file", target_path="rules.py")], "file_inspection_budget_exhausted", 2),
            (LoopLimits(max_iterations=3, max_model_calls=3, max_file_inspections=2, max_file_modifications=1, max_repairs=1),
             [decision("write_text", target_path="service.py", content="# one\n"), decision("write_text", target_path="rules.py", content="# two\n")], "file_modification_budget_exhausted", 2),
        ]
        for limits, responses, reason, calls in cases:
            with self.subTest(reason=reason):
                record, provider = self.run_loop(responses, limits=limits)
                self.assert_truthful_failure(record, reason)
                self.assertEqual(provider.calls, calls)

    def test_repair_budget_exhaustion_is_post_failure_and_non_pass(self):
        record, _ = self.run_loop([
            decision("run_tests"),
            decision("write_text", target_path="service.py", content="# ineffective\n"),
            decision("run_tests"),
            decision("write_text", target_path="service.py", content="# still ineffective\n")],
            limits=LoopLimits(max_iterations=5, max_model_calls=5, max_file_inspections=2,
                              max_file_modifications=3, max_repairs=1))
        self.assert_truthful_failure(record, "repair_budget_exhausted")
        self.assertEqual(record["budget_usage"]["repairs"], 1)

    def test_malformed_policy_and_independent_action_authorization(self):
        original = (self.workspace / "rules.py").read_text(encoding="utf-8")
        malformed, _ = self.run_loop(["{not-json"])
        self.assert_truthful_failure(malformed, "schema_validation_failure")
        self.assertEqual((self.workspace / "rules.py").read_text(encoding="utf-8"), original)
        outside = self.workspace.parent / "outside.py"
        record, _ = self.run_loop([
            decision("write_text", target_path="rules.py", content="OFFSET = 9\n"),
            decision("write_text", target_path="../outside.py", content="forbidden")])
        self.assert_truthful_failure(record, "policy_violation")
        self.assertFalse(outside.exists())
        self.assertEqual(record["cycles"][0]["policy_validation"]["status"], "PASS")
        self.assertEqual(record["cycles"][1]["policy_validation"]["status"], "FAIL")

    def test_progress_guards_and_false_success_claim(self):
        same = decision("inspect_file", target_path="service.py")
        record, _ = self.run_loop([same, same, same])
        self.assert_truthful_failure(record, "repeated_identical_action")
        self.assertEqual(record["budget_usage"]["file_inspections"], 2)
        record, _ = self.run_loop([decision("run_tests"), decision("run_tests")])
        self.assert_truthful_failure(record, "retest_without_change")
        record, _ = self.run_loop([decision("run_tests"), decision("finish")])
        self.assert_truthful_failure(record, "model_finished_without_passing_tests")

    def test_provider_and_tool_failures_are_truthful(self):
        record, provider = self.run_loop([ProviderError("localhost unavailable", 503)])
        self.assert_truthful_failure(record, "provider_failure")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(record["execution"]["endpoint"], "http://127.0.0.1:8080/v1")
        tools = ExplodingTestTools(self.workspace)
        record, _ = self.run_loop([decision("run_tests")], tools=tools)
        self.assert_truthful_failure(record, "execution_failure")

    def _assert_reconstructable(self, record):
        for key in ("submitted_task", "run_id", "started_at", "ended_at", "execution", "limits",
                    "budget_usage", "cycles", "inspected_paths", "modified_paths", "test_results",
                    "progress_guard_events", "deterministic_verification", "terminal_reason", "status", "errors"):
            self.assertIn(key, record)
        self.assertEqual(record["execution"]["endpoint"], "http://127.0.0.1:8080/v1")
        self.assertEqual(record["execution"]["model"], MODEL)
        self.assertEqual([c["iteration"] for c in record["cycles"]], list(range(1, len(record["cycles"]) + 1)))
        for stamp in (record["started_at"], record["ended_at"]):
            datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        for cycle in record["cycles"]:
            self.assertIsNotNone(cycle["ended_at"])
            self.assertIn(cycle["schema_validation"]["status"], {"PASS", "FAIL"})
            self.assertIsNotNone(cycle["budget_before"])
            self.assertIsNotNone(cycle["budget_after"])


if __name__ == "__main__":
    unittest.main()
