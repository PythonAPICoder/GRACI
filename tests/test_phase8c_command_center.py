"""Phase 8C trusted reactive presence and accessible command-center tests."""

import json
import re
import unittest
from pathlib import Path

from graci.visualizer import SystemState


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "graci" / "visualizer_ui"


class TrustedPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (UI / "index.html").read_text("utf-8")
        cls.css = (UI / "visualizer.css").read_text("utf-8")
        cls.js = (UI / "visualizer.js").read_text("utf-8")

    def test_every_resident_state_has_deterministic_semantic_copy(self):
        block = re.search(
            r"PRESENTATION_BY_STATE = Object\.freeze\(\{(.*?)\}\);",
            self.js,
            re.S,
        ).group(1)
        states = set(re.findall(r'^\s*"([a-z_]+)":\[', block, re.M))
        self.assertEqual(states, {state.value for state in SystemState})
        for label in ("READY", "LISTENING", "PROCESSING", "REVIEWING",
                      "SPEAKING", "DEGRADED", "FAILED"):
            self.assertIn(f'["{label}"', block)
        self.assertIn('presentation=PRESENTATION_BY_STATE[s.system_state]||', self.js)

    def test_qwen_and_glm_are_active_only_from_observed_agent_state(self):
        self.assertIn('agent.state==="active"', self.js)
        self.assertIn("QWEN · IMPLEMENTER", self.html)
        self.assertIn("GLM · REVIEWER", self.html)
        self.assertIn('aria-label="Qwen primary local implementer"', self.html)
        self.assertIn('aria-label="GLM local reviewer and verifier"', self.html)

    def test_4090_semantics_are_reason_specific_and_fail_closed(self):
        for label in ("UNAVAILABLE — BLOCKED — MO2 RUNNING", "UNAVAILABLE — UNHEALTHY",
                      "UNAVAILABLE — POLICY", "UNKNOWN — FAIL CLOSED",
                      "AVAILABLE / HEALTHY", "IN USE"):
            self.assertIn(label, self.js)
        mo2 = self.js.index('node.mo2_state==="running"')
        unhealthy = self.js.index('node.endpoint_health==="unhealthy"')
        eligibility = self.js.index('node.eligible!==true')
        self.assertLess(mo2, unhealthy)
        self.assertLess(unhealthy, eligibility)
        self.assertNotIn("ModOrganizer.exe", self.js)

    def test_3090_unknown_health_is_not_described_as_fail_closed(self):
        primary = ('node.node_id==="3090"&&node.endpoint_health!=="healthy"'
                   ')return ["unknown","HEALTH NOT OBSERVED"]')
        self.assertIn(primary, self.js)
        self.assertLess(self.js.index(primary), self.js.index(
            'if(node.endpoint_health!=="healthy")return '
            '["unknown","UNKNOWN — FAIL CLOSED"]'))

    def test_latest_completed_response_currency_is_truthful(self):
        self.assertIn("renderLatestTurn(turn, newerTurnActive=false)", self.js)
        self.assertIn("PREVIOUS COMPLETED · NEW TURN ACTIVE", self.js)
        self.assertIn('Boolean(s.task.task_id)&&!["completed","failed"]', self.js)
        self.assertIn('turn.response_available?turn.response_text:', self.js)
        self.assertNotIn('$("operator-response").innerHTML', self.js)

    def test_accessibility_reduced_motion_and_responsive_contract(self):
        self.assertIn('role="status" aria-live="polite" aria-atomic="true"', self.html)
        self.assertIn('aria-labelledby="latest-turn-label" aria-live="polite" aria-atomic="true"', self.html)
        self.assertIn("focus-visible", self.css)
        reduced = self.css[self.css.index("@media(prefers-reduced-motion:reduce)"):]
        self.assertIn("animation:none!important", reduced)
        self.assertIn("transition:none!important", reduced)
        self.assertIn("@media(max-width:720px)", self.css)

    def test_pointer_and_physical_spacebar_contract_is_unchanged(self):
        self.assertIn('button.addEventListener("pointerdown"', self.js)
        self.assertIn('button.addEventListener("pointerup"', self.js)
        self.assertIn('event.code!=="Space"', self.js)
        self.assertIn("event.repeat", self.js)
        self.assertIn("editableTarget(event.target)", self.js)
        self.assertIn("finishPTT(generation)", self.js)

    def test_no_authority_surface_or_fictional_activity_was_added(self):
        qa_panel = re.search(
            r'<section id="processing-audio-test-panel"([^>]*)>(.*?)</section>',
            self.html,
            re.S,
        )
        self.assertIsNotNone(qa_panel)
        self.assertRegex(qa_panel.group(1), r"\bhidden\b")
        qa_modes = re.findall(
            r'<button\b[^>]*\bdata-processing-audio-test="([^"]+)"',
            qa_panel.group(2),
        )
        self.assertEqual(qa_modes, ["ui-confirmation", "qwen", "glm"])
        normal_html = self.html[:qa_panel.start()] + self.html[qa_panel.end():]
        self.assertEqual(
            set(re.findall(r'<button\b[^>]*\bid="([^"]+)"', normal_html)),
            {"ptt-button", "ui-sounds", "restart-button", "end-session"},
        )
        self.assertEqual(len(re.findall(r"<button\b", normal_html)), 4)
        self.assertIn(
            'const processingAudioDiagnosticsEnabled = '
            'window.location.hash==="#processing-audio-diagnostics";',
            self.js,
        )
        self.assertIn(
            "function installProcessingAudioDiagnostics(){"
            "if(!processingAudioDiagnosticsEnabled)return;",
            self.js,
        )
        self.assertIn('panel.hidden=false', self.js)
        self.assertIn('.processing-audio-test-panel[hidden]{display:none}', self.css)
        self.assertIn('id="ui-sounds"', self.html)
        self.assertIn('id="end-session"', self.html)
        combined = (self.html + self.js).lower()
        for forbidden in ("fake progress", "token stream", "model selector",
                          "4090 override", "wake word", "speechsynthesis"):
            self.assertNotIn(forbidden, combined)


class Phase8CEvidenceTests(unittest.TestCase):
    def test_evidence_records_manual_acceptance_boundary(self):
        evidence = json.loads((ROOT / "phase8c" / "evidence" /
                               "phase8c-closure.json").read_text("utf-8"))
        self.assertEqual(evidence["phase"], "8C")
        self.assertEqual(evidence["starting_commit"],
                         "8fde138bbf021310f57b91cf298af6b80f2a2573")
        self.assertFalse(evidence["authority_boundary"]["new_execution_authority"])
        self.assertFalse(evidence["authority_boundary"]["new_routes"])
        self.assertEqual(evidence["reactive_presence_audit"]["classification"], "B")
        self.assertFalse(evidence["phase8d_handoff"]["implemented_in_phase8c"])
        self.assertEqual(len(evidence["phase8d_handoff"]["physical_qa_capability_gaps"]), 2)
        self.assertEqual(evidence["physical_browser_qa"]["status"],
                         "PRODUCT_OWNER_FINDINGS_REPAIRED_REVIEW_PENDING")


if __name__ == "__main__":
    unittest.main()
