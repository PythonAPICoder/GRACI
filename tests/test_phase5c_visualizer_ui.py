"""Phase 5C static serving, observer boundary, fixture, and UI contract tests."""

import http.client
import json
import re
import unittest
from pathlib import Path

from graci.visualizer import EventSeverity, SystemState
from graci.visualizer_backend import BASE_PATH, VisualizerServer, VisualizerStateProvider
from phase5c.synthetic import STATES, lifecycle

ROOT = Path(__file__).parents[1]
UI = ROOT / "graci" / "visualizer_ui"


class ServerCase(unittest.TestCase):
    def setUp(self):
        self.provider = VisualizerStateProvider(); self.server = VisualizerServer(self.provider, port=0); self.server.start()
    def tearDown(self): self.server.stop()
    def request(self, method, path, body=None):
        connection=http.client.HTTPConnection("127.0.0.1", self.server.bound_port, timeout=2)
        connection.request(method,path,body=body,headers={"Host":f"127.0.0.1:{self.server.bound_port}"})
        response=connection.getresponse(); data=response.read(); result=response.status,dict(response.getheaders()),data; connection.close(); return result

    def test_root_and_known_assets_have_exact_types_and_csp(self):
        for path, mime, marker in (("/","text/html; charset=utf-8",b"G.R.A.C.I."),("/visualizer.css","text/css; charset=utf-8",b"prefers-reduced-motion"),("/visualizer.js","text/javascript; charset=utf-8",b"EventSource")):
            status,headers,body=self.request("GET",path); self.assertEqual(status,200); self.assertEqual(headers["Content-Type"],mime); self.assertIn(marker,body); self.assertIn("default-src 'self'",headers["Content-Security-Policy"])
            self.assertEqual(self.request("HEAD",path)[2],b"")

    def test_unknown_directory_repo_file_and_traversal_are_unavailable(self):
        for path in ("/unknown.js","/graci/","/PROJECT_STATE.md","/.git/config"): self.assertEqual(self.request("GET",path)[0],404)
        for path in ("/../PROJECT_STATE.md","/%2e%2e/PROJECT_STATE.md","/%252e%252e/PROJECT_STATE.md","/graci%5cvisualizer.py"):
            self.assertIn(self.request("GET",path)[0],(400,404))

    def test_api_unaffected_and_every_mutation_rejected(self):
        self.assertEqual(self.request("GET",f"{BASE_PATH}/health")[0],200)
        self.assertEqual(self.request("GET",f"{BASE_PATH}/snapshot")[0],503)
        for method in ("POST","PUT","PATCH","DELETE","OPTIONS"):
            self.assertEqual(self.request(method,"/",b"upload")[0],405)
        for route in ("task","memory","routing","inference","upload","control"):
            self.assertEqual(self.request("GET",f"{BASE_PATH}/{route}")[0],404)
        self.assertIsNone(self.provider.snapshot()); self.assertEqual(self.provider.events(),())


class StaticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(UI/"index.html").read_text("utf-8"); cls.css=(UI/"visualizer.css").read_text("utf-8"); cls.js=(UI/"visualizer.js").read_text("utf-8")

    def test_offline_no_remote_fonts_cdn_analytics_or_controls(self):
        combined=self.html+self.css+self.js
        for forbidden in ("http://","https://","@import","googleapis","analytics","task-entry","prompt-entry","model selector","approve","reject","memory_content","chain_of_thought","stdout","stderr"):
            self.assertNotIn(forbidden.lower(),combined.lower())
        self.assertNotRegex(self.html,r"<(?:form|input|button|textarea|select)\b")

    def test_paths_bounds_polling_disconnect_and_all_contract_enums(self):
        for suffix in ("/health","/snapshot","/events","/events/stream"): self.assertIn(f'${{API}}{suffix}',self.js)
        self.assertIn("MAX_EVENT_ROWS = 100",self.js); self.assertRegex(self.js,r"SNAPSHOT_INTERVAL_MS = [2-5]000")
        self.assertIn("DISCONNECTED",self.js); self.assertIn("STALE",self.js)
        for item in SystemState: self.assertIn(f'"{item.value}"',self.js)
        for item in EventSeverity: self.assertIn(f'"{item.value}"',self.js)

    def test_distinct_architecture_markup_and_reduced_motion(self):
        for marker in ('id="node-3090"','id="node-4090"','id="agent-qwen"','id="agent-glm"','id="review-panel"','id="adjudication-panel"','data-field="mo2"'):
            self.assertIn(marker,self.html)
        for stage in ("memory","qwen","tools","tests","review","adjudication"): self.assertIn(f'data-stage="{stage}"',self.html)
        for marker in ('class="core-orbit primary-orbit"','class="core-orbit secondary-orbit"','class="signal-node node-a"','class="signal-node node-e"'):
            self.assertIn(marker,self.html)
        for marker in ("orbit-flow","orbit-flow-reverse","listening-ripple","speaking-pulse","success-pulse"):
            self.assertIn(marker,self.css)
        self.assertIn("prefers-reduced-motion:reduce",self.css)

    def test_synthetic_lifecycle_is_valid_internal_only_and_complete(self):
        snapshots,events=lifecycle(); blocked,_=lifecycle(blocked_4090=True)
        self.assertEqual(tuple(item.system_state for item in snapshots),STATES)
        self.assertTrue(all(json.loads(__import__("graci.visualizer",fromlist=["serialize_visualizer"]).serialize_visualizer(item)) for item in snapshots+events))
        self.assertFalse(blocked[3].compute.optional_4090.eligible)
        source=(ROOT/"phase5c"/"synthetic.py").read_text("utf-8")
        self.assertNotIn("VisualizerStateProvider",source); self.assertNotIn("visualizer_backend",source)

    def test_phase5c_acceptance_evidence_is_valid_and_passed(self):
        evidence=json.loads((ROOT/"phase5c"/"evidence"/"phase5c-acceptance.json").read_text("utf-8"))
        self.assertEqual(evidence["starting_commit"],"7a12d4c42a9ac1951c47653ce11048c2da346df8")
        self.assertEqual(evidence["status"],"PASS")
        self.assertTrue(evidence["security"]["observer_only"])


if __name__ == "__main__": unittest.main()
