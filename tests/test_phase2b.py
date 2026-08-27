"""Deterministic Phase 2B governed multi-step autonomy tests."""
import json, tempfile, unittest
from pathlib import Path

from graci.autonomous import AutonomousRepairController, LoopLimits
from graci.config import Config
from graci.provider import ProviderResponse

MODEL = "qwen3.8-27b-q4_k_m"

def decision(action, **values):
    return json.dumps({"schema_version": 1, "action": action, **values, "rationale": "bounded"})

class Provider:
    def __init__(self, responses): self.responses, self.contexts = list(responses), []
    def propose_repair_decision(self, task, context):
        self.contexts.append(context)
        return ProviderResponse(200, self.responses.pop(0), MODEL)

class Phase2BTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd()); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name); self.workspace, self.runs = root / "fixture", root / "runs"
        (self.workspace / "tests").mkdir(parents=True)
        (self.workspace / "pricing.py").write_text("from rates import RATE\n\ndef total(value):\n    return value - RATE\n", encoding="utf-8")
        (self.workspace / "rates.py").write_text("RATE = 3\n", encoding="utf-8")
        (self.workspace / "tests" / "test_pricing.py").write_text(
            "import unittest\nfrom pricing import total\n\nclass Tests(unittest.TestCase):\n    def test_total(self):\n        self.assertEqual(total(10), 12)\n", encoding="utf-8")
        self.config = Config(run_directory=self.runs)

    def run_loop(self, responses, limits=None):
        provider = Provider(responses)
        controller = AutonomousRepairController(self.workspace,
            readable_files=["pricing.py", "rates.py", "tests/test_pricing.py"],
            editable_files=["pricing.py", "rates.py"], provider=provider, config=self.config,
            limits=limits or LoopLimits(max_iterations=12, max_model_calls=12,
                max_file_inspections=6, max_file_modifications=4, max_repairs=3))
        record = controller.run("Repair all defects and verify tests.")
        self.assertEqual(record, json.loads((self.runs / f"{record['run_id']}.json").read_text(encoding="utf-8")))
        return record, provider

    def test_multifile_success_has_two_independently_governed_modifications(self):
        record, _ = self.run_loop([
            decision("list_files"), decision("inspect_file", target_path="pricing.py"),
            decision("inspect_file", target_path="rates.py"),
            decision("write_text", target_path="pricing.py", content="from rates import RATE\n\ndef total(value):\n    return value + RATE\n"),
            decision("write_text", target_path="rates.py", content="RATE = 2\n"), decision("run_tests")])
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["modified_paths"], ["pricing.py", "rates.py"])
        self.assertEqual(record["inspected_paths"], ["pricing.py", "rates.py"])
        self.assertEqual(record["budget_usage"]["file_modifications"], 2)
        self.assertTrue(all(c["policy_validation"]["status"] == "PASS" for c in record["cycles"]))

    def test_failed_test_feedback_drives_later_repair(self):
        record, provider = self.run_loop([
            decision("write_text", target_path="pricing.py", content="from rates import RATE\n\ndef total(value):\n    return value + RATE\n"),
            decision("run_tests"), decision("write_text", target_path="rates.py", content="RATE = 2\n"), decision("run_tests")])
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["budget_usage"]["repairs"], 1)
        self.assertIn("AssertionError", provider.contexts[2]["recent_cycles"][-1]["tool_result"]["command_result"]["stderr"])

    def test_valid_first_write_invalid_second_write_fails_closed(self):
        outside = self.workspace.parent / "outside.py"
        record, _ = self.run_loop([
            decision("write_text", target_path="pricing.py", content="# valid\n"),
            decision("write_text", target_path="../outside.py", content="forbidden")])
        self.assertEqual(record["status"], "FAIL"); self.assertEqual(record["terminal_reason"], "policy_violation")
        self.assertEqual((self.workspace / "pricing.py").read_text(), "# valid\n"); self.assertFalse(outside.exists())
        self.assertEqual(record["cycles"][1]["workspace_validation"]["status"], "FAIL")

    def test_inspection_and_modification_budgets(self):
        limits = LoopLimits(max_iterations=4, max_model_calls=4, max_file_inspections=1, max_file_modifications=1, max_repairs=2)
        record, _ = self.run_loop([decision("inspect_file", target_path="pricing.py"), decision("inspect_file", target_path="rates.py")], limits)
        self.assertEqual(record["terminal_reason"], "file_inspection_budget_exhausted")
        record, _ = self.run_loop([decision("write_text", target_path="pricing.py", content="# one\n"), decision("write_text", target_path="rates.py", content="# two\n")], limits)
        self.assertEqual(record["terminal_reason"], "file_modification_budget_exhausted")

    def test_model_call_and_repair_budgets(self):
        limits = LoopLimits(max_iterations=3, max_model_calls=1, max_file_inspections=3, max_file_modifications=3, max_repairs=2)
        record, _ = self.run_loop([decision("list_files")], limits)
        self.assertEqual(record["terminal_reason"], "model_call_budget_exhausted")
        limits = LoopLimits(max_iterations=5, max_model_calls=5, max_file_inspections=2, max_file_modifications=3, max_repairs=1)
        record, _ = self.run_loop([decision("run_tests"), decision("write_text", target_path="pricing.py", content="# still bad\n"), decision("write_text", target_path="rates.py", content="# denied\n")], limits)
        self.assertEqual(record["terminal_reason"], "repair_budget_exhausted")

    def test_progress_guards_stop_repeats(self):
        same = decision("inspect_file", target_path="pricing.py")
        record, _ = self.run_loop([same, same, same])
        self.assertEqual(record["terminal_reason"], "repeated_identical_action")
        self.assertEqual(record["budget_usage"]["file_inspections"], 2)
        record, _ = self.run_loop([decision("run_tests"), decision("run_tests")])
        self.assertEqual(record["terminal_reason"], "retest_without_change")

    def test_context_truncation_is_recorded_and_evidence_ordered(self):
        limits = LoopLimits(max_iterations=3, max_model_calls=3, max_file_inspections=2,
                            max_file_modifications=2, max_repairs=2, max_context_characters=10)
        record, provider = self.run_loop([decision("inspect_file", target_path="pricing.py"), decision("finish")], limits)
        self.assertTrue(record["context_events"]); self.assertEqual(len(provider.contexts[1]["recent_cycles"][-1]["tool_result"]["content"]), 10)
        self.assertEqual([c["iteration"] for c in record["cycles"]], [1, 2])
        self.assertTrue(all(c["budget_before"] and c["budget_after"] for c in record["cycles"]))

if __name__ == "__main__": unittest.main()
