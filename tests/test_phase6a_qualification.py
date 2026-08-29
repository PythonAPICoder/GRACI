import json
import unittest
from pathlib import Path

from phase6a.pronunciation import speech_presentation_text

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
        self.assertTrue(data["tts_audition"]["selection_finalized"])
        self.assertEqual(data["tts_audition"]["user_selected_voice"], "af_bella")

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

    def test_project_state_marks_phase6a_complete(self):
        first = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")[:600]
        self.assertIn("Phase 5 — COMPLETE", first)
        self.assertIn("Phase 6 — COMPLETE", first)
        self.assertNotIn("Phase 6 — IN PROGRESS", first)
        self.assertIn("Phase 6A — COMPLETE", first)
        self.assertIn("Phase 6B — COMPLETE", first)

    def test_pronunciation_override_is_bounded_whole_token_and_speech_only(self):
        source = "GRACI uses 3090 and 4090. GRACIOUS, XGRACI, 13090, 4090X, and 5090 remain unchanged."
        rendered = speech_presentation_text(source)
        self.assertEqual(rendered, "GRAY-see uses thirty ninety and forty ninety. GRACIOUS, XGRACI, 13090, 4090X, and 5090 remain unchanged.")
        self.assertEqual(source, "GRACI uses 3090 and 4090. GRACIOUS, XGRACI, 13090, 4090X, and 5090 remain unchanged.")
        with self.assertRaises(ValueError):
            speech_presentation_text("x" * 20_001)

    def test_finalist_evidence_preserves_authoritative_sentences(self):
        evidence = json.loads((ROOT / "phase6a/artifacts/audition/finalist-af_bella/pronunciation-audition.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["voice"], "af_bella")
        self.assertFalse(evidence["authoritative_text_mutated"])
        self.assertEqual(len(evidence["results"]), 4)
        for row in evidence["results"]:
            self.assertIn("GRACI", row["authoritative_source_text"])
            self.assertNotIn("GRAY-see", row["authoritative_source_text"])
            self.assertIn("GRAY-see", row["speech_presentation_text"])

    def test_technical_pronunciation_qa_preserves_source_and_is_explicit(self):
        evidence = json.loads((ROOT / "phase6a/artifacts/audition/technical-pronunciation-af_bella/technical-pronunciation-qa.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["explicit_pronunciations"], {
            "GRACI": "GRAY-see", "3090": "thirty ninety", "4090": "forty ninety"})
        self.assertFalse(evidence["generic_number_rewriting"])
        self.assertFalse(evidence["authoritative_text_mutated"])
        self.assertEqual(len(evidence["results"]), 4)
        for row in evidence["results"]:
            self.assertNotIn("thirty ninety", row["authoritative_source_text"])
            self.assertNotIn("forty ninety", row["authoritative_source_text"])

if __name__ == "__main__":
    unittest.main()
