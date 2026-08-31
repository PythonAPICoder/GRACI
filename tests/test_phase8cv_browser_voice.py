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
                       'id="node-3090" class="telemetry-panel telemetry-primary"',
                       'id="node-4090" class="telemetry-panel telemetry-optional"',
                       'class="status-compact"', 'class="compact-actions"',
                       'latest-turn-footer"', 'id="end-session"'):
            self.assertIn(marker, self.html)
        self.assertNotIn('class="detail-rail status-rail"', self.html)
        for marker in ("grid-template-columns:480px minmax(0,1fr) 480px",
                       "width:min(1070px", ".telemetry-panel{",
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
        self.assertIn('id="speech-radial"', self.html)
        self.assertIn('id="speech-energy-ring"', self.html)
        self.assertIn('id="secondary-radial"', self.html)
        self.assertIn('id="calibration-ticks"', self.html)
        self.assertIn('class="hud-structural-arcs"', self.html)
        self.assertIn("for(let i=0;i<96;i++)", self.js)
        self.assertIn("for(let i=0;i<120;i++)", self.js)
        self.assertIn("circuit-primary", self.html)
        self.assertIn("circuit-packets", self.html)
        for marker in ('body[data-circuit-mode="qwen"] .circuit-packet',
                       'body[data-circuit-mode="glm"] .circuit-packet',
                       "animation-name:circuit-packet-reverse",
                       "@keyframes circuit-packet-forward"):
            self.assertIn(marker, self.css)
        self.assertIn('document.body.dataset.activeAgent=activeAgent', self.js)
        self.assertIn('document.body.dataset.circuitMode=circuitPresentationMode(s)',
                      self.js)

    def test_outer_speech_ring_is_complete_uniform_and_bounded(self):
        self.assertEqual(self.html.count('id="speech-energy-ring"'), 1)
        self.assertIn(
            '<circle id="speech-energy-ring" class="speech-energy-ring" '
            'cx="500" cy="500" r="414"/>', self.html)
        self.assertIn(
            'class="orb-inner-rim" cx="500" cy="500" r="247"', self.html)
        self.assertIn(
            'class="orb-energy-rim" cx="500" cy="500" r="260" '
            'stroke="url(#newRim)"', self.html)
        for marker in (
                '.speech-energy-ring{--speech-ring-core-feather:.65px;',
                'blur(var(--speech-ring-core-feather))',
                '--speech-ring-tight-bloom:3px',
                'fill:none;stroke:currentColor;',
                'stroke-width:5.4px;opacity:.16;',
                'body[data-system-state="speaking"] .speech-energy-ring',
                'stroke-width:calc(5.4px + var(--voice-energy,0)*12.6px)',
                'opacity:calc(.16 + var(--voice-energy,0)*.8)',
                '--speech-ring-tight-bloom:3px',
                '--speech-ring-broad-bloom:5px',
                'calc(3px + var(--voice-energy,0)*7px)',
                'calc(5px + var(--voice-energy,0)*23px)'):
            self.assertIn(marker, self.css)
        ring_css = self.css[self.css.index('.speech-energy-ring{'):
                            self.css.index('\n', self.css.index('.speech-energy-ring{'))]
        for forbidden in ('stroke-dasharray', 'animation:', 'rotate(', 'scaleY('):
            self.assertNotIn(forbidden, ring_css)
        self.assertLessEqual(.16 + .8, 1)
        self.assertEqual(5.4 + 12.6, 18)
        self.assertEqual(3 + 7, 10)
        self.assertEqual(5 + 23, 28)
        self.assertIn(
            'previous*.72+raw*.75', self.js)
        self.assertIn(
            'setProperty("--voice-energy",energy.toFixed(3))', self.js)
        self.assertIn(
            'setProperty("--voice-energy","0")', self.js)
        self.assertNotIn('for(let i=0;i<64;i++)', self.js)
        self.assertNotIn('document.querySelectorAll("#speech-radial line")', self.js)
        self.assertNotIn('.speech-radial line', self.css)
        self.assertNotIn('--bar', self.js + self.css)

    def test_nucleus_is_layered_and_audio_modulation_stays_bounded(self):
        for marker in ('id="hexSurfaceMask"', 'id="hexRimMask"',
                       'class="orb-hex-rim"', 'class="orb-hex-highlights"'):
            self.assertIn(marker, self.html)
        for marker in ("var(--voice-energy)*.025", "var(--voice-energy)*.22",
                       "var(--voice-energy)*1.8px"):
            self.assertIn(marker, self.css)
        self.assertEqual(self.js.count("createAnalyser()"), 1)

    def test_status_gadget_uses_existing_analyser_and_is_semantically_bounded(self):
        self.assertIn('id="status-activity-label"', self.html)
        self.assertIn('document.querySelectorAll("#status-waveform i")', self.js)
        self.assertIn('data[bin]/255)*1.55', self.js)
        self.assertIn('bar.style.setProperty("--live","0")', self.js)
        for label in ("VOICE OUTPUT", "PROCESSING ACTIVITY", "REVIEW ACTIVITY",
                      "LISTENING"):
            self.assertIn(label, self.js)
        for marker in ('body[data-system-state="speaking"] .status-waveform i',
                       'var(--live,0)*34',
                       'body[data-active-agent="qwen"]:not([data-system-state="speaking"])',
                       'body[data-active-agent="glm"]:not([data-system-state="speaking"])',
                       'body[data-system-state="listening"] .status-waveform i'):
            self.assertIn(marker, self.css)
        self.assertIn('.status-waveform i{display:block;width:3px;min-height:3px;height:3px',
                      self.css)
        self.assertNotIn('height:calc(var(--wave)*1px)', self.css)
        self.assertNotIn('var(--voice-energy)*38', self.css)

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
