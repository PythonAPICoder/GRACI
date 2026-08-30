"""Deterministic contracts for the final processing-presence polish."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "graci" / "visualizer_ui"


class ProcessingSoundContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (UI / "visualizer.js").read_text("utf-8")
        cls.sound_block = cls.js[
            cls.js.index("function processingSoundMode"):
            cls.js.index("function renderStatusRail")
        ]

    def test_qwen_and_glm_use_distinct_sparse_deterministic_profiles(self):
        profiles = self.js[
            self.js.index("const PROCESSING_SOUND_PROFILES"):
            self.js.index("const PRESENTATION_BY_STATE")
        ]
        for marker in (
            'qwen:Object.freeze({wave:"triangle"',
            'glm:Object.freeze({wave:"sine"',
            "delays:Object.freeze([2100,3900,2700,5100,3200])",
            "delays:Object.freeze([2800,4700,3400,5600])",
            "gain:.032", "gain:.026", "duration:.12", "duration:.135",
            "initialDelay:700", "initialDelay:800",
        ):
            self.assertIn(marker, profiles)
        self.assertNotIn("Math.random", self.sound_block)
        self.assertIn("profile.frequencies[sound.sequence%profile.frequencies.length]",
                      self.sound_block)

    def test_trusted_states_select_qwen_or_glm_and_suppress_listening_speaking(self):
        selector = self.sound_block[
            self.sound_block.index("function processingSoundMode"):
            self.sound_block.index("function ensureProcessingAudio")
        ]
        for marker in (
            'snapshot.system_state==="listening"',
            'snapshot.system_state==="speaking"',
            'snapshot.agents.glm.state==="active"',
            'snapshot.agents.qwen.state==="active"',
        ):
            self.assertIn(marker, selector)
        self.assertIn("return null", selector)

    def test_autoplay_lifecycle_is_armed_by_operator_gestures(self):
        for marker in (
            "function ensureProcessingAudio", 'context.state==="suspended"',
            "await context.resume().catch", "armProcessingAudio();",
            'event.code==="Space"', 'toggle.addEventListener("click"',
        ):
            self.assertIn(marker, self.js)
        self.assertIn('sound.context?.suspend().catch', self.js)
        self.assertIn('sound.context?.close().catch', self.js)

    def test_suppression_and_exit_cancel_one_bounded_timer(self):
        allowed = self.sound_block[
            self.sound_block.index("function processingSoundAllowed"):
            self.sound_block.index("function scheduleProcessingSound")
        ]
        for marker in (
            "sound.enabled", "!document.hidden", 'ptt.phase==="idle"',
            "!playback.artifactId", "sound.generation===generation",
            "processingSoundMode(state.snapshot)===mode", "clearTimeout(sound.timer)",
            "sound.generation+=1", "sound.timer=setTimeout",
        ):
            self.assertIn(marker, allowed)
        self.assertNotIn("setInterval", self.sound_block)
        self.assertEqual(self.sound_block.count("sound.timer=setTimeout"), 1)

    def test_chirp_graph_is_audible_bounded_and_reaches_destination(self):
        profiles = self.js[
            self.js.index("const PROCESSING_SOUND_PROFILES"):
            self.js.index("const PRESENTATION_BY_STATE")
        ]
        gains = [float(value) for value in re.findall(r"gain:(\.\d+)", profiles)]
        durations = [float(value) for value in re.findall(r"duration:(\.\d+)", profiles)]
        initial_delays = [int(value) for value in re.findall(r"initialDelay:(\d+)", profiles)]
        self.assertEqual(len(gains), 2)
        self.assertTrue(all(gain >= .02 for gain in gains))
        self.assertTrue(all(.08 <= duration <= .16 for duration in durations))
        self.assertTrue(all(600 <= delay <= 1000 for delay in initial_delays))
        for marker in (
            "oscillator.connect(gain)", "gain.connect(context.destination)",
            'oscillator.addEventListener("ended"', "oscillator.start(now)",
            "oscillator.stop(now+profile.duration+.016)",
            'recordProcessingAudioDiagnostic("cue-started"',
            "destinationConnected:true", 'recordProcessingAudioDiagnostic("cue-completed"',
        ):
            self.assertIn(marker, self.sound_block)

    def test_opt_in_audio_diagnostics_are_bounded_and_normal_ui_is_quiet(self):
        diagnostic = self.js[
            self.js.index("const PROCESSING_AUDIO_DIAGNOSTIC_LIMIT"):
            self.js.index("const PRESENTATION_BY_STATE")
        ]
        self.assertIn("PROCESSING_AUDIO_DIAGNOSTIC_LIMIT = 12", diagnostic)
        self.assertIn('window.location.hash==="#processing-audio-diagnostics"', diagnostic)
        self.assertIn("processingAudioDiagnostics.shift()", diagnostic)
        self.assertIn("document.documentElement.dataset.processingAudioDiagnostic=JSON.stringify(processingAudioDiagnostics)", diagnostic)
        self.assertIn('Object.defineProperty(window,"__graciProcessingAudioDiagnostics"', diagnostic)
        self.assertNotIn("console.", diagnostic)


class CircuitPresenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (UI / "index.html").read_text("utf-8")
        cls.css = (UI / "visualizer.css").read_text("utf-8")
        cls.js = (UI / "visualizer.js").read_text("utf-8")

    def test_packet_pool_is_bounded_precreated_and_has_layered_short_trails(self):
        packets = re.findall(
            r'<g class="circuit-packet packet-\d+">(.*?)</g>',
            self.html, flags=re.DOTALL)
        self.assertEqual(len(packets), 6)
        for packet in packets:
            self.assertEqual(packet.count("<path"), 3)
            self.assertEqual(packet.count('pathLength="100"'), 3)
            self.assertEqual(packet.count('class="packet-trail'), 2)
            self.assertEqual(packet.count('class="packet-head"'), 1)
        self.assertEqual(self.html.count('class="packet-trail packet-trail-far"'), 6)
        self.assertEqual(self.html.count('class="packet-trail packet-trail-near"'), 6)
        self.assertEqual(self.html.count('class="packet-head"'), 6)
        for marker in (
            ".packet-trail-far{stroke-width:5.4;stroke-dasharray:6.2 93.8",
            ".packet-trail-near{stroke-width:3.2;stroke-dasharray:3.1 96.9",
            ".packet-head{stroke-width:3.8;stroke-dasharray:.65 99.35",
        ):
            self.assertIn(marker, self.css)

    def test_trusted_state_mapping_is_explicit_and_fail_closed(self):
        mapping = self.js[
            self.js.index("function circuitPresentationMode"):
            self.js.index("function processingSoundMode")
        ]
        for marker in (
            'return "warning"', 'return "speaking"', 'return "listening"',
            'return "glm"', 'return "qwen"', 'return "completed"',
            'return snapshot.system_state', 'return "idle"',
        ):
            self.assertIn(marker, mapping)
        self.assertIn("document.body.dataset.circuitMode=circuitPresentationMode(s)",
                      self.js)

    def test_idle_qwen_glm_speaking_profiles_differ_without_sync(self):
        for marker in (
            'body[data-circuit-mode="idle"] .packet-1',
            'body[data-circuit-mode="idle"] .packet-4',
            "--packet-duration:31s", "--packet-duration:37s",
            'body[data-circuit-mode="qwen"] .circuit-packet',
            "--trail-near-opacity:.54", "--packet-duration:5.3s",
            "--packet-duration:6.7s", "--packet-duration:8.6s",
            'body[data-circuit-mode="glm"] .circuit-packet',
            "color:#a56cff", "animation-name:circuit-packet-reverse-head",
            'body[data-circuit-mode="speaking"] .packet-1',
            'body[data-circuit-mode="speaking"] .packet-4',
            "--packet-opacity:.15", "--packet-opacity:.13",
            "--packet-delay:-8.3s", "--packet-delay:-14.2s",
        ):
            self.assertIn(marker, self.css)
        self.assertIn("--trail-far-opacity:.12", self.css)
        self.assertNotIn("animation:circuit-pulse 14s", self.css)

    def test_forward_and_reverse_trails_remain_behind_the_leading_point(self):
        for marker in (
            ".packet-trail-far{stroke-width:5.4;stroke-dasharray:6.2 93.8;stroke-dashoffset:106.2",
            "animation-name:circuit-packet-forward-far",
            ".packet-trail-near{stroke-width:3.2;stroke-dasharray:3.1 96.9;stroke-dashoffset:103.1",
            "animation-name:circuit-packet-forward-near",
            ".packet-head{stroke-width:3.8;stroke-dasharray:.65 99.35;stroke-dashoffset:100",
            "animation-name:circuit-packet-forward-head",
            'body[data-circuit-mode="glm"] .packet-trail-far{stroke-dashoffset:-.65;animation-name:circuit-packet-reverse-far}',
            'body[data-circuit-mode="glm"] .packet-trail-near{stroke-dashoffset:-.65;animation-name:circuit-packet-reverse-near}',
            'body[data-circuit-mode="glm"] .packet-head{stroke-dashoffset:0;animation-name:circuit-packet-reverse-head}',
            "@keyframes circuit-packet-reverse-head{from{stroke-dashoffset:0}to{stroke-dashoffset:100}}",
        ):
            self.assertIn(marker, self.css)
        self.assertNotIn('body[data-circuit-mode="glm"] .circuit-packet path{animation-name:', self.css)

    def test_reduced_motion_hides_only_traveling_packets(self):
        reduced_rules = re.findall(
            r"@media\(prefers-reduced-motion:reduce\)\{[^\n]+",
            self.css)
        self.assertTrue(any(".circuit-packet{display:none!important}" in rule
                            for rule in reduced_rules))
        self.assertIn('class="circuit-layer circuit-primary"', self.html)
        self.assertIn('class="circuit-layer circuit-detail"', self.html)

    def test_circuit_presentation_has_no_inference_or_unbounded_loop_semantics(self):
        mapping = self.js[
            self.js.index("function circuitPresentationMode"):
            self.js.index("function processingSoundMode")
        ].lower()
        for forbidden in ("token", "throughput", "confidence", "percent",
                          "requestanimationframe", "setinterval", "settimeout"):
            self.assertNotIn(forbidden, mapping)
        self.assertNotIn("createElementNS", mapping)


class GaugePolishContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (UI / "index.html").read_text("utf-8")
        cls.css = (UI / "visualizer.css").read_text("utf-8")
        cls.js = (UI / "visualizer.js").read_text("utf-8")

    def test_all_eight_gauges_share_static_glass_and_specular_layers(self):
        self.assertEqual(self.html.count('class="telemetry-gauge'), 8)
        self.assertEqual(self.html.count('class="gauge-glass"'), 8)
        self.assertEqual(self.html.count('class="gauge-specular"'), 8)
        gauge_css = self.css[
            self.css.rindex("/* Final physical-QA telemetry presentation"):
            self.css.index(".operator-control{", self.css.rindex(
                "/* Final physical-QA telemetry presentation"))
        ]
        for marker in (
            ".telemetry-gauge .gauge-glass", "linear-gradient(145deg",
            "radial-gradient(circle at 30% 24%", "inset -9px -11px 20px",
            ".telemetry-gauge .gauge-specular", "border-top:2px solid",
            "clip-path:polygon", "pointer-events:none",
        ):
            self.assertIn(marker, gauge_css)
        self.assertNotIn("animation:", gauge_css)

    def test_memory_gauges_keep_shared_circle_and_readable_capacity_text(self):
        self.assertEqual(self.html.count("telemetry-gauge telemetry-memory"), 4)
        self.assertIn(".telemetry-memory>i b{font-size:.72rem", self.css)
        self.assertIn(".telemetry-memory>i b{font-size:.58rem", self.css)
        for marker in (
            'metric(root,"vram",vram===null?"—"',
            'metric(root,"ram",ram===null?"—"',
            '`${(telemetry.vram_used_mib/1024).toFixed(1)} / ',
            '`${(telemetry.ram_used_mib/1024).toFixed(1)} / ',
        ):
            self.assertIn(marker, self.js)

    def test_stale_unavailable_gauges_remain_empty_desaturated_and_labeled(self):
        for marker in (
            'root.dataset.telemetry=fresh?"fresh":observed?"stale"',
            'clearTelemetry(root,observed?"STALE":"NOT OBSERVED")',
            'item.style.setProperty("--meter","0deg")',
            '.telemetry-panel:not([data-telemetry="fresh"]) .telemetry-gauge>i',
            "filter:saturate(.28) brightness(.74)",
            '.telemetry-panel:not([data-telemetry="fresh"]) .gauge-glass',
        ):
            self.assertIn(marker, self.js + self.css)
        for node_id in ("node-3090", "node-4090"):
            start = self.html.index(f'id="{node_id}"')
            panel = self.html[start:self.html.index("</aside>", start)]
            self.assertNotIn("CPU TEMP", panel)
            self.assertNotIn("GPU TEMP", panel)


if __name__ == "__main__":
    unittest.main()
