"""Phase 8C-V bounded browser playback and reactive-presence acceptance."""

import http.client
import json
import threading
import time
import unittest
from pathlib import Path

from graci.browser_playback import BrowserPlaybackBroker, BrowserPlaybackError
from graci.playback import PlaybackStatus
from graci.tts import SynthesizedAudio
from graci.visualizer import SystemState
from graci.visualizer_backend import BASE_PATH, VisualizerServer, VisualizerStateProvider
from graci.voice_lifecycle import VoiceLifecycle


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "graci" / "visualizer_ui"


def audio():
    return SynthesizedAudio(b"RIFF-authorized-kokoro", 24_000, 1, 2, .25)


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.lifecycle = VoiceLifecycle()
        self.broker = BrowserPlaybackBroker(self.lifecycle, claim_seconds=.15)

    def begin_play(self):
        result = []
        thread = threading.Thread(target=lambda: result.append(self.broker.play(audio())))
        thread.start()
        for _ in range(100):
            available = self.broker.available()
            if available:
                return thread, result, available
            time.sleep(.005)
        self.fail("artifact did not become available")

    def test_available_claim_start_complete_and_exact_audio(self):
        thread, result, available = self.begin_play()
        claim = self.broker.claim(available["artifact_id"], "browser-client-00000001")
        self.assertEqual(self.broker.audio(claim["artifact_id"], claim["claim_token"]),
                         audio().wav_bytes)
        self.assertEqual(self.lifecycle.state, SystemState.IDLE)
        self.broker.acknowledge(claim["artifact_id"], claim["claim_token"], "started")
        self.assertEqual(self.lifecycle.state, SystemState.SPEAKING)
        self.broker.acknowledge(claim["artifact_id"], claim["claim_token"], "completed")
        thread.join(1)
        self.assertEqual(result[0].status, PlaybackStatus.SUCCESS)
        self.assertEqual(self.lifecycle.state, SystemState.IDLE)
        self.assertIsNone(self.broker.available())

    def test_single_claim_stale_tokens_cancel_and_timeout(self):
        thread, result, available = self.begin_play()
        claim = self.broker.claim(available["artifact_id"], "browser-client-00000001")
        with self.assertRaises(BrowserPlaybackError):
            self.broker.claim(available["artifact_id"], "browser-client-00000002")
        with self.assertRaises(BrowserPlaybackError):
            self.broker.audio(available["artifact_id"], "not-a-valid-claim-token-value")
        self.broker.stop(); thread.join(1)
        self.assertEqual(result[0].status, PlaybackStatus.CANCELLED)
        thread, result, available = self.begin_play()
        self.broker.claim(available["artifact_id"], "browser-client-00000003")
        time.sleep(.2); self.broker.available(); thread.join(1)
        self.assertEqual(result[0].status, PlaybackStatus.TIMEOUT)

    def test_only_synthesized_audio_is_accepted(self):
        with self.assertRaises(TypeError):
            self.broker.play(Path("C:/Windows/win.ini"))


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.broker = BrowserPlaybackBroker(claim_seconds=.2)
        self.server = VisualizerServer(VisualizerStateProvider(), port=0,
                                       browser_playback=self.broker)
        self.server.start()

    def tearDown(self):
        self.broker.stop(); self.server.stop()

    def request(self, method, path, body=b"", headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.bound_port, timeout=2)
        base = {"Host": f"127.0.0.1:{self.server.bound_port}"}
        base.update(headers or {})
        connection.request(method, path, body=body, headers=base)
        response = connection.getresponse(); payload = response.read(); status = response.status
        response_headers = dict(response.getheaders()); connection.close()
        return status, response_headers, payload

    def post(self, route, value):
        return self.request("POST", f"{BASE_PATH}{route}", json.dumps(value).encode(),
                            {"Content-Type":"application/json"})

    def test_audio_route_is_claim_bounded_not_a_file_server(self):
        holder = []
        thread = threading.Thread(target=lambda: holder.append(self.broker.play(audio())))
        thread.start()
        for _ in range(100):
            status, _, body = self.request("GET", f"{BASE_PATH}/speech/available")
            available = json.loads(body)["audio"]
            if available: break
            time.sleep(.005)
        status, _, body = self.post("/speech/claim", {
            "artifact_id":available["artifact_id"], "client_id":"browser-client-00000001"})
        self.assertEqual(status, 200); claim = json.loads(body)
        status, headers, body = self.request(
            "GET", f"{BASE_PATH}/speech/audio/{claim['artifact_id']}", headers={
                "X-GRACI-Speech-Claim":claim["claim_token"]})
        self.assertEqual((status, headers["Content-Type"], body),
                         (200, "audio/wav", audio().wav_bytes))
        self.assertEqual(self.request("GET", f"{BASE_PATH}/speech/audio/win.ini")[0], 410)
        self.broker.stop(); thread.join(1)


class BrowserContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (UI / "index.html").read_text("utf-8")
        cls.css = (UI / "visualizer.css").read_text("utf-8")
        cls.js = (UI / "visualizer.js").read_text("utf-8")

    def test_actual_web_audio_path_and_bounded_analysis(self):
        for marker in ("new Audio(", "createMediaElementSource", "createAnalyser",
                       "getByteFrequencyData", "smoothingTimeConstant=.72",
                       "Math.max(0,Math.min(1", "requestAnimationFrame(analyzeVoice)",
                       "cancelAnimationFrame"):
            self.assertIn(marker, self.js)
        self.assertNotIn("speechSynthesis", self.js)

    def test_visual_state_sounds_suppression_and_accessibility(self):
        self.assertIn('id="speech-radial"', self.html)
        self.assertIn('id="ui-sounds"', self.html)
        for marker in ("snapshot.agents.glm.state", "snapshot.agents.qwen.state",
                       "document.hidden", 'ptt.phase!=="idle"', "playback.artifactId",
                       "localStorage.setItem", "clearTimeout", "prefers-reduced-motion"):
            self.assertIn(marker, self.js + self.css)
        self.assertIn("circuit-drift", self.css)

    def test_physical_qa_layout_hierarchy_is_compact_and_centered(self):
        for marker in ('class="graci-presence"', 'class="presence-circuitry"',
                       'status-rail"', 'class="compact-actions"',
                       'latest-turn-footer"', 'id="end-session"'):
            self.assertIn(marker, self.html)
        for marker in ("grid-template-columns:minmax(0,1fr) 360px",
                       "width:min(1070px", ".detail-rail.status-rail",
                       ".lower-grid{display:none}", ".pipeline{height:58px;display:grid"):
            self.assertIn(marker, self.css)

    def test_approved_branding_orb_and_dense_environment_contract(self):
        self.assertNotIn("GRAY-see", self.html)
        for marker in ('class="presence-system"', 'class="orb-aura"',
                       'class="orb-sphere"', 'class="orb-inner-rim"',
                       'class="orb-horizon"', 'id="newRim"'):
            self.assertIn(marker, self.html)
        for marker in ('class="circuit-layer circuit-depth"',
                       'class="circuit-layer circuit-primary"',
                       'class="circuit-layer circuit-secondary"',
                       'class="circuit-layer circuit-detail"',
                       'class="circuit-layer circuit-underlay"',
                       'class="circuit-layer circuit-micro"',
                       'class="circuit-glints"',
                       'class="circuit-packets"', 'class="signal-nodes"',
                       'class="indicator"'):
            self.assertIn(marker, self.html)
        self.assertIn('r="490"', self.html)
        self.assertIn('r="260"', self.html)

    def test_radial_circuit_and_state_mapping_remain_truthful(self):
        self.assertIn("for(let i=0;i<64;i++)", self.js)
        self.assertIn('id="speech-radial"', self.html)
        self.assertIn("circuit-primary", self.html)
        self.assertIn("circuit-packets", self.html)
        for marker in ('body[data-active-agent="qwen"] .circuit-packets',
                       'body[data-active-agent="glm"] .circuit-packets',
                       "animation-direction:reverse", "@keyframes circuit-pulse",
                       "transform:scaleY(.82)", "var(--bar,0)*.5"):
            self.assertIn(marker, self.css)
        self.assertIn('document.body.dataset.activeAgent=activeAgent', self.js)

    def test_compact_controls_are_presentation_only(self):
        self.assertIn('id="ptt-button"', self.html)
        self.assertIn('id="restart-button"', self.html)
        self.assertIn('id="ui-sounds"', self.html)
        self.assertIn("endPresentationSession", self.js)
        self.assertIn('stopBrowserPlayback("session_ended")', self.js)
        self.assertNotIn('/end-session', self.js)

    def test_autoplay_and_interruptions_are_truthful(self):
        for marker in ("NotAllowedError", "autoplay_rejected", 'speechAck("started")',
                       'speechAck("completed")', 'speechAck("cancelled"',
                       '"ptt_interrupted"', '"operator_interrupted"'):
            self.assertIn(marker, self.js)


if __name__ == "__main__":
    unittest.main()
