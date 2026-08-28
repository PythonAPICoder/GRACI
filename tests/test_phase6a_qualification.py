import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Phase6AQualificationTests(unittest.TestCase):
    def test_config_is_bounded_local_and_cpu_first(self):
        data = json.loads((ROOT / "phase6a/qualification_config.json").read_text(encoding="utf-8"))
        self.assertTrue(data["local_only"])
        self.assertFalse(data["network_runtime_allowed"])
        self.assertLessEqual(data["max_audio_seconds"], 120)
        self.assertEqual(data["stt"][0]["device"], "cpu")

    def test_evidence_contract_and_phase_boundary(self):
        data = json.loads((ROOT / "phase6a/evidence/phase6a-qualification.json").read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(len(data["stt_results"]), 3)
        self.assertFalse(data["runtime_integration_added"])
        self.assertTrue(all(not value for value in data["boundaries"].values()))
        self.assertTrue(data["tts_audition"]["user_selection_required"])

    def test_no_private_audio_or_model_cache_is_tracked(self):
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("phase6a/cache/", ignored)
        self.assertIn("phase6a/.venv/", ignored)
        manifest = json.loads((ROOT / "phase6a/artifacts/piper-generation.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["synthetic_non_private"])

    def test_architecture_preserves_authority_boundary(self):
        text = (ROOT / "phase6a/ARCHITECTURE.md").read_text(encoding="utf-8")
        for phrase in ("untrusted user input", "authoritative final user-facing response", "must not authorize tools", "must not"):
            self.assertIn(phrase, text)

    def test_project_state_marks_phase6a_current(self):
        first = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")[:600]
        self.assertIn("Phase 5 — COMPLETE", first)
        self.assertIn("Phase 6 — IN PROGRESS", first)
        self.assertIn("Phase 6A — CURRENT", first)

if __name__ == "__main__":
    unittest.main()
