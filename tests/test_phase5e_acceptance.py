"""Phase 5E closure evidence and reconstructibility checks."""

import json
import unittest
from pathlib import Path

from graci.registry import GLM_MODEL_ID, QWEN_MODEL_ID
from graci.visualizer import SystemState
from graci.visualizer_backend import BASE_PATH, DEFAULT_HOST, DEFAULT_PORT


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "phase5e" / "evidence" / "phase5e-closure.json"
README = ROOT / "phase5e" / "README.md"


class Phase5EClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(EVIDENCE.read_text("utf-8"))
        cls.documentation = README.read_text("utf-8")

    def test_closure_evidence_is_passed_and_phase6_not_started(self):
        self.assertEqual(self.evidence["status"], "PASS")
        self.assertTrue(self.evidence["phase5_complete"])
        self.assertFalse(self.evidence["phase6_started"])
        self.assertEqual(self.evidence["defects_found"], 0)

    def test_all_contract_states_are_recorded_exactly(self):
        self.assertEqual(self.evidence["accepted_states"],
                         [state.value for state in SystemState])
        self.assertTrue(self.evidence["contract_immutable"])
        self.assertEqual(self.evidence["event_limit"], 100)

    def test_real_qwen_identity_and_truthful_terminal_result(self):
        live = self.evidence["real_qwen"]
        self.assertEqual(live["status"], "PASS")
        self.assertEqual(live["server_reported_model"], QWEN_MODEL_ID)
        self.assertEqual(live["node"], "3090-primary-localhost")
        self.assertEqual(live["terminal_reason"], "tests_passed")
        self.assertEqual(live["states"],
                         ["planning", "retrieving_memory", "reasoning",
                          "testing", "completed"])

    def test_backend_and_ui_remain_read_only_local_and_offline(self):
        backend = self.evidence["backend"]
        self.assertEqual((DEFAULT_HOST, DEFAULT_PORT), ("127.0.0.1", 8766))
        self.assertTrue(all(path.startswith(BASE_PATH) for path in backend["api_paths"]))
        self.assertEqual(backend["read_methods"], ["GET", "HEAD"])
        self.assertFalse(backend["cors"])
        self.assertFalse(backend["control_endpoints"])
        self.assertFalse(self.evidence["ui"]["remote_assets"])

    def test_privacy_failure_isolation_and_routing_authority(self):
        self.assertTrue(all(value is False for key, value in self.evidence["privacy"].items()
                            if key.endswith("exposed")))
        self.assertTrue(self.evidence["failure_isolation"]["observer_exceptions_contained"])
        self.assertFalse(self.evidence["failure_isolation"]["disconnect_fabricates_failure"])
        self.assertTrue(self.evidence["routing"]["primary_3090_authority"])
        self.assertTrue(self.evidence["routing"]["optional_4090_only"])
        self.assertFalse(self.evidence["routing"]["visualizer_controls_routing"])

    def test_documentation_is_self_contained_and_records_exact_models(self):
        for required in (QWEN_MODEL_ID, GLM_MODEL_ID, "127.0.0.1:8766",
                         "prefers-reduced-motion", "Phase 5", "Phase 6"):
            self.assertIn(required, self.documentation)


if __name__ == "__main__":
    unittest.main()
