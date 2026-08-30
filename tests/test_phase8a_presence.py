"""Phase 8A observer-only visual-presence contract tests."""
import http.client
import json
import re
import unittest
from pathlib import Path

from graci.visualizer import SystemState
from graci.visualizer_backend import BASE_PATH, VisualizerServer, VisualizerStateProvider

ROOT = Path(__file__).parents[1]
UI = ROOT / "graci" / "visualizer_ui"


class PresenceSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (UI / "index.html").read_text("utf-8")
        cls.css = (UI / "visualizer.css").read_text("utf-8")
        cls.js = (UI / "visualizer.js").read_text("utf-8")

    def test_every_authoritative_state_has_one_bounded_presence(self):
        block = re.search(r"PRESENCE_BY_STATE = Object\.freeze\(\{(.*?)\}\);", self.js, re.S).group(1)
        mapping = dict(re.findall(r'"([a-z_]+)":\"([a-z]+)\"', block))
        self.assertEqual(set(mapping), {state.value for state in SystemState})
        self.assertEqual(set(mapping.values()), {"resting", "receptive", "thinking", "acting", "validating", "responding", "success", "warning", "failure"})
        expected = {"idle":"resting", "listening":"receptive", "reasoning":"thinking", "executing_tool":"acting", "reviewing":"validating", "speaking":"responding", "completed":"success", "warning":"warning", "failed":"failure"}
        for state, presence in expected.items(): self.assertEqual(mapping[state], presence)

    def test_unknown_is_warning_and_authoritative_label_is_rendered(self):
        self.assertIn('const SAFE_PRESENCE = "warning"', self.js)
        self.assertIn('$("overall-state").textContent=text(s.system_state,"UNKNOWN")', self.js)
        self.assertIn('$("core-state").textContent=text(s.system_state,"UNKNOWN")', self.js)
        self.assertIn('id="presence-category"', self.html)

    def test_static_semantics_stale_and_reduced_motion_are_explicit(self):
        for category in ("resting", "receptive", "thinking", "acting", "validating", "responding", "success", "warning", "failure"):
            self.assertIn(f'data-presence="{category}"', self.css)
        self.assertIn('data-connection="disconnected"', self.css)
        self.assertIn('content:" · STALE"', self.css)
        reduced = self.css[self.css.index("@media(prefers-reduced-motion:reduce)"):]
        self.assertIn("animation:none!important", reduced)
        self.assertIn("transition:none!important", reduced)

    def test_presence_panels_have_only_the_later_explicit_ptt_control(self):
        combined = (self.html + self.css + self.js).lower()
        self.assertNotRegex(self.html, r"<(?:form|input|textarea|select)\b")
        self.assertEqual(len(re.findall(r"<button\b", self.html)), 4)
        self.assertIn('id="restart-button"', self.html)
        self.assertIn('id="ptt-button"', self.html)
        presentation = combined.replace("http://www.w3.org/2000/svg", "")
        for forbidden in ("http://", "https://", "speechsynthesis", "wake word", "websocket", "analytics"):
            self.assertNotIn(forbidden, presentation)
        for authority in ("routing", "model selector", "memory write", "command execution"):
            self.assertNotIn(authority, combined)

    def test_3090_and_mo2_truth_remain_visible(self):
        self.assertIn("PRIMARY / AUTHORITY", self.html)
        self.assertIn("OPTIONAL CAPACITY", self.html)
        self.assertIn("BLOCKED — MO2 RUNNING", self.js)


class ObserverBoundaryTests(unittest.TestCase):
    def test_static_allowlist_and_mutation_boundary_are_unchanged(self):
        source = (ROOT / "graci" / "visualizer_backend.py").read_text("utf-8")
        for asset in ('"/"', '"/visualizer.css"', '"/visualizer.js"'): self.assertIn(asset, source)
        provider = VisualizerStateProvider(); server = VisualizerServer(provider, port=0); server.start()
        try:
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                connection = http.client.HTTPConnection("127.0.0.1", server.bound_port, timeout=2)
                connection.request(method, f"{BASE_PATH}/snapshot", body=b"control")
                response = connection.getresponse(); response.read(); connection.close()
                self.assertEqual(response.status, 405)
            self.assertIsNone(provider.snapshot()); self.assertEqual(provider.events(), ())
        finally: server.stop()

    def test_phase8a_evidence_contract(self):
        evidence = json.loads((ROOT / "phase8a" / "evidence" / "phase8a-closure.json").read_text("utf-8"))
        self.assertEqual(evidence["starting_commit"], "20e6ba3ee9b730a8f3adc53dbbe3ee836a042f17")
        self.assertEqual(evidence["phase"], "8A")
        self.assertEqual(evidence["status"], "PASS")
        self.assertTrue(evidence["security_boundary"]["observer_only"])
        self.assertTrue(evidence["compute_policy"]["primary_3090_independently_sufficient"])


if __name__ == "__main__": unittest.main()
