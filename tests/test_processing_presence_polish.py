"""Deterministic contracts for the final processing-presence polish."""

import re
import subprocess
import unittest
from pathlib import Path

from graci.observation import ObservationKind, observe
from graci.registry import GLM_MODEL_ID, QWEN_MODEL_ID
from graci.visualizer_backend import VisualizerStateProvider
from graci.visualizer_runtime import VisualizerRuntimeObserver


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "graci" / "visualizer_ui"
SCHEDULER_HARNESS = ROOT / "tests" / "processing_audio_scheduler_harness.js"


class ProcessingSoundBehaviorTests(unittest.TestCase):
    def run_scenario(self, name):
        result = subprocess.run(
            ["node", "--unhandled-rejections=strict", str(SCHEDULER_HARNESS), name],
            cwd=ROOT, capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            f"scheduler scenario {name!r} failed\nstdout:\n{result.stdout}"
            f"stderr:\n{result.stderr}",
        )

    def test_disconnect_blocks_and_cancels_processing_timers(self):
        self.run_scenario("connection-trust")

    def test_browser_speech_claim_cancels_processing_before_playback(self):
        self.run_scenario("speech-claim-cancellation")

    def test_exact_diagnostic_rechecks_safety_after_context_resume(self):
        self.run_scenario("diagnostic-post-resume-recheck")

    def test_exact_diagnostic_packet_clusters_and_modes_cannot_overlap(self):
        self.run_scenario("diagnostic-no-overlap")

    def test_scheduler_has_no_orphan_or_duplicate_rescheduling(self):
        self.run_scenario("no-orphan-or-duplicate-scheduling")

    def test_ui_confirmation_fails_closed_across_urgent_resume_transitions(self):
        self.run_scenario("ui-confirmation-suppression-races")

    def test_refresh_and_unsafe_state_cancellation_boundaries(self):
        self.run_scenario("cue-refresh-cancellation-boundaries")

    def test_thinking_pulse_event_feeds_audio_and_existing_circuit_route(self):
        self.run_scenario("thinking-pulse-event-coherence")

    def test_candidate_one_profile_and_event_stream_are_exact_and_deterministic(self):
        self.run_scenario("data-chatter-profile-and-determinism")

    def test_trusted_qwen_and_glm_drive_the_production_scheduler(self):
        self.run_scenario("thinking-pulse-production-lifecycle")

    def test_thinking_pulse_cancels_at_every_urgent_boundary(self):
        self.run_scenario("thinking-pulse-cancellation-boundaries")

    def test_trusted_stop_fence_blocks_stale_qwen_but_allows_glm_review(self):
        self.run_scenario("thinking-pulse-stop-fence-transitions")

    def test_ui_sounds_and_reduced_motion_preserve_safe_pulse_semantics(self):
        self.run_scenario("thinking-pulse-ui-sounds-and-reduced-motion")

    def test_thinking_pulse_resources_remain_bounded(self):
        self.run_scenario("thinking-pulse-bounded-resources")

    def test_thinking_pulse_fixed_bounded_audition_sequence(self):
        self.run_scenario("thinking-pulse-audition-sequence")


class ProcessingSoundContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (UI / "visualizer.js").read_text("utf-8")
        cls.sound_block = cls.js[
            cls.js.index("function processingSoundMode"):
            cls.js.index("function renderStatusRail")
        ]

    def test_candidate_one_data_chatter_parameters_are_authoritative(self):
        profile = self.js[
            self.js.index("const THINKING_PULSE_DATA_CHATTER"):
            self.js.index("const THINKING_PULSE_LIMITS")
        ]
        for marker in (
            'id:"data-chatter",seed:7481201,masterGain:2.1960059',
            'baseFrequencyHz:Object.freeze([1250,6100])',
            'maximumRenderedFrequencyHz:10500',
            'weightedPulseOption("sine",.56)',
            'weightedPulseOption("triangle",.30)',
            'weightedPulseOption("square",.14)',
            'weightedPulseOption("click",.50)',
            'weightedPulseOption("pip",.35)',
            'weightedPulseOption("sweep",.10)',
            'weightedPulseOption("dual",.05)',
            'click:Object.freeze([20,44])',
            'pip:Object.freeze([32,78])',
            'sweep:Object.freeze([52,116])',
            'dual:Object.freeze([54,108])',
            'eventGain:Object.freeze([.10,.25])',
            'initialDelayMs:Object.freeze([80,150])',
            'intraClusterSpacingMs:Object.freeze([22,64])',
            'postClusterSilenceMs:Object.freeze([65,210])',
            'sweepDownRatio:Object.freeze([.62,.84])',
            'sweepUpRatio:Object.freeze([1.18,1.48])',
            'dualToneRatio:Object.freeze([1.31,1.71])',
            'dualSecondaryGain:Object.freeze([.26,.42])',
            'pan:Object.freeze([-.18,.18]),auditionDurationMs:10000',
        ):
            self.assertIn(marker, profile)
        self.assertNotIn(".mp3", self.js.lower())

    def test_qwen_and_glm_share_audio_character_with_bounded_visual_distinction(self):
        profiles = self.js[
            self.js.index("const THINKING_PULSE_PROFILES"):
            self.js.index("const THINKING_PULSE_EVENT_TYPES")
        ]
        self.assertIn(
            'colorHues:Object.freeze([168,186,202,222,252,288,322,28])',
            profiles)
        self.assertIn(
            'routes:Object.freeze([1,2,3,4,5,6,7,8,9,10,11,12,13,14])',
            profiles)
        self.assertIn(
            'colorHues:Object.freeze([254,264,276,288,302])', profiles)
        self.assertIn(
            'routes:Object.freeze([1,2,4,5,7,8,10,12,14])', profiles)
        self.assertIn('direction:"forward"', profiles)
        self.assertIn('direction:"reverse"', profiles)
        audio_profile = self.js[
            self.js.index("function thinkingPulseAudioProfile"):
            self.js.index("function canStartProcessingCue")
        ]
        self.assertNotIn("qwen", audio_profile)
        self.assertNotIn("glm", audio_profile)
        self.assertNotIn("event.profile", audio_profile)

    def test_trusted_states_select_qwen_or_glm_and_fail_closed(self):
        selector = self.sound_block[
            self.sound_block.index("function processingSoundMode"):
            self.sound_block.index("function ensureProcessingAudio")
        ]
        for marker in (
            "THINKING_PULSE_PROCESSING_STATES.includes(snapshot.system_state)",
            'snapshot.agents.glm.state==="active"',
            'snapshot.agents.qwen.state==="active"',
        ):
            self.assertIn(marker, selector)
        self.assertIn("return null", selector)

    def test_production_scheduler_generates_each_micro_event_dynamically(self):
        production = self.js[
            self.js.index("function queueProcessingPulse"):
            self.js.index("function diagnosticCueBlockReason")
        ]
        for marker in (
            "nextDataChatterEvent(thinkingPulse.productionGenerator,mode,0)",
            'dispatchThinkingPulseEvent(event,"production")',
            "thinkingPulse.productionEventCount+=1",
            "nextDelay=event.spacingMs",
            "queueProcessingPulse(mode,generation,nextDelay)",
            "createThinkingPulseGenerator(`${state.snapshot?.task?.task_id||\"no-task\"}|${mode}`)",
            "thinkingPulse.productionGenerator.initialDelayMs",
            "if(sound.mode!==mode)scheduleProcessingSound(mode)",
            "sound.timer===null&&!sound.pending&&thinkingPulse.productionGenerator",
        ):
            self.assertIn(marker, production)
        self.assertEqual(production.count("sound.timer=setTimeout"), 1)
        self.assertNotIn("setInterval", production)
        self.assertNotIn("new Audio(", production)

    def test_one_dispatch_uses_one_existing_packet_and_the_shared_audio_context(self):
        dispatch = self.js[
            self.js.index("function dispatchThinkingPulseEvent"):
            self.js.index("function thinkingPulseAuditionSafetyReason")
        ]
        self.assertEqual(dispatch.count("launchThinkingPulseVisual(event)"), 1)
        self.assertEqual(dispatch.count("startProcessingCue("), 1)
        visual = self.js[
            self.js.index("function launchThinkingPulseVisual"):
            self.js.index("function thinkingPulseAudioProfile")
        ]
        self.assertIn(
            'document.querySelector(`.circuit-packet.packet-${event.route}`)',
            visual)
        self.assertNotIn("createElement", visual)
        graph = self.js[
            self.js.index("function startProcessingCue"):
            self.js.index("function uiSoundsConfirmationBlockReason")
        ]
        for marker in (
            "const context=sound.context,gain=context.createGain()",
            "sound.activeCues.add(cue)",
            "gain.connect(context.destination)",
            "context.createOscillator()", "context.createGain()",
            "context.createStereoPanner()",
            "oscillator.frequency.exponentialRampToValueAtTime(voice.endFrequency,voiceAt+voice.duration)",
            "oscillator.stop(voiceAt+voice.duration+.006)",
            "sound.activeCues.delete(cue)",
        ):
            self.assertIn(marker, graph)
        self.assertNotIn("new AudioContext", graph)
        self.assertNotIn("createAnalyser", graph)

    def test_stop_fence_and_urgent_boundaries_cancel_immediately(self):
        bridge = self.js[
            self.js.index("const THINKING_PULSE_STOP_EVENTS"):
            self.js.index("function connectEvents")
        ]
        for marker in (
            'voice_listening:"listening"', 'voice_speaking:"speaking"',
            'qwen_completed:"completed"', 'glm_completed:"completed"',
            'task_completed:"completed"', 'task_failed:"failed"',
            'task_started:"all"', 'qwen_started:"qwen"',
            'glm_started:"glm"', 'review_started:"glm"',
            "function updateThinkingPulseStopFence(event)",
            "function queueSnapshotRefresh(event)",
            "if(stopReason)cancelProcessingSounds(stopReason,true)",
        ):
            self.assertIn(marker, bridge)
        allowed = self.sound_block[
            self.sound_block.index("function processingPttPhaseAllowed"):
            self.sound_block.index("function diagnosticCueBlockReason")
        ]
        for marker in (
            "function thinkingPulseStopFenceReason(mode,snapshot=state.snapshot)",
            'return `trusted_stop_${fence.eventType}`',
            "clearTimeout(sound.timer)", "sound.generation+=1",
            "stopActiveProcessingCues(reason,includeDiagnostic)",
            "clearAllThinkingPulseVisuals()",
            'cancelProcessingSounds("ptt_start",true)',
            'cancelProcessingSounds("browser_playback",true)',
        ):
            self.assertIn(marker, self.js if marker.startswith("cancel") else allowed)

    def test_ui_sounds_off_mutes_nodes_without_destroying_visual_scheduler(self):
        presentation = self.js[
            self.js.index("function installPresentation"):
            self.js.index("async function start()")
        ]
        off = (
            'if(!sound.enabled){stopActiveProcessingCues("ui_sounds_off",true);'
            'sound.context?.suspend().catch(()=>{});}'
        )
        on = (
            'else{if(thinkingPulse.running||sound.mode||'
            'processingSoundMode(state.snapshot))armProcessingAudio();'
            'else playUiSoundsConfirmation();if(state.snapshot)'
            'updateProcessingSounds(state.snapshot);}'
        )
        self.assertIn(off, presentation)
        self.assertIn(on, presentation)
        self.assertNotIn('cancelProcessingSounds("ui_sounds_off"', presentation)

    def test_reduced_motion_and_resource_bounds_are_explicit(self):
        for marker in (
            "motionSuppressed=reducedMotion.matches",
            "const visualStarted=motionSuppressed?false:launchThinkingPulseVisual(event)",
            "if(reducedMotion.matches)clearAllThinkingPulseVisuals()",
            "maxActiveCues:6", "routeCount:14",
            "activeCues:new Set()", "activeVisuals:new Map()",
            "event.packetDurationMs+140",
        ):
            self.assertIn(marker, self.js)
        self.assertEqual(self.js.count("createAnalyser()"), 1)
        self.assertEqual(self.js.count("new AudioContext()"), 3)
        self.assertEqual(self.js.count("requestAnimationFrame("), 1)

    def test_opt_in_audio_diagnostics_are_bounded_and_normal_ui_is_quiet(self):
        diagnostic = self.js[
            self.js.index("const PROCESSING_AUDIO_DIAGNOSTIC_LIMIT"):
            self.js.index("const PRESENTATION_BY_STATE")
        ]
        self.assertIn("PROCESSING_AUDIO_DIAGNOSTIC_LIMIT = 96", diagnostic)
        self.assertIn('window.location.hash==="#processing-audio-diagnostics"',
                      diagnostic)
        self.assertIn("processingAudioDiagnostics.shift()", diagnostic)
        self.assertIn(
            'Object.defineProperty(window,"__graciProcessingAudioDiagnostics"',
            diagnostic)
        self.assertNotIn("console.", diagnostic)

    def test_real_browser_submitting_phase_allows_only_trusted_processing(self):
        finish = self.js[
            self.js.index("async function finishPTT"):
            self.js.index("async function cancelPTT")
        ]
        allowed = self.sound_block[
            self.sound_block.index("function processingPttPhaseAllowed"):
            self.sound_block.index("function processingSoundBlockReason")
        ]
        self.assertIn('ptt.phase="submitting"', finish)
        self.assertIn('finally{if(generation===ptt.generation)resetPTT();}', finish)
        self.assertIn('ptt.phase==="idle"||ptt.phase==="submitting"', allowed)
        self.assertIn('if(!processingPttPhaseAllowed())return `ptt_${ptt.phase}`',
                      allowed)
        self.assertIn('cancelProcessingSounds("ptt_start",true)', self.js)

    def test_real_runtime_lifecycle_projects_qwen_and_glm_trusted_states(self):
        provider = VisualizerStateProvider()
        observer = VisualizerRuntimeObserver(provider)
        observe(observer, ObservationKind.TASK_STARTED, "presence-real-state",
                summary="real production mapping")
        observe(observer, ObservationKind.MODEL_STARTED, "presence-real-state",
                role="implementer", model=QWEN_MODEL_ID, node="3090")
        qwen = provider.snapshot()
        self.assertEqual(qwen.system_state.value, "reasoning")
        self.assertEqual(qwen.agents.qwen.state.value, "active")
        self.assertEqual(qwen.agents.glm.state.value, "inactive")
        observe(observer, ObservationKind.MODEL_COMPLETED, "presence-real-state",
                role="implementer", model=QWEN_MODEL_ID, node="3090")
        observe(observer, ObservationKind.REVIEW_STARTED, "presence-real-state",
                model=GLM_MODEL_ID, node="3090")
        glm = provider.snapshot()
        self.assertEqual(glm.system_state.value, "reviewing")
        self.assertEqual(glm.agents.qwen.state.value, "completed")
        self.assertEqual(glm.agents.glm.state.value, "active")

    def test_every_real_lifecycle_sse_event_queues_a_bounded_snapshot_refresh(self):
        bridge = self.js[
            self.js.index("const OBSERVED_EVENT_TYPES"):
            self.js.index("function tick")
        ]
        for event_type in (
            "task_started", "qwen_started", "qwen_completed",
            "glm_started", "glm_completed", "review_started",
            "voice_listening", "voice_speaking", "task_completed",
        ):
            self.assertIn(f'"{event_type}"', bridge)
        for marker in (
            "function queueSnapshotRefresh(event)",
            "clearTimeout(state.snapshotRefreshTimer)",
            "state.snapshotRefreshTimer=setTimeout",
            "refreshSnapshot();},25)",
            "queueSnapshotRefresh(event)",
            'recordProcessingAudioDiagnostic("trusted-event"',
            'recordProcessingAudioDiagnostic("presentation-state"',
            "eventTimestamp:event.timestamp", "pttPhase:ptt.phase",
        ):
            self.assertIn(marker, self.js)


class CircuitPresenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (UI / "index.html").read_text("utf-8")
        cls.css = (UI / "visualizer.css").read_text("utf-8")
        cls.js = (UI / "visualizer.js").read_text("utf-8")

    def test_fourteen_precreated_layered_routes_cover_the_full_stage(self):
        packets = re.findall(
            r'<g class="circuit-packet packet-(\d+)">(.*?)</g>',
            self.html, flags=re.DOTALL)
        self.assertEqual([int(number) for number, _ in packets], list(range(1, 15)))
        topology = {"left": 0, "right": 0, "top": 0, "bottom": 0}
        for _, packet in packets:
            paths = re.findall(r'<path class="([^"]+)" pathLength="100" d="([^"]+)"',
                               packet)
            self.assertEqual([name for name, _ in paths], [
                "packet-trail packet-trail-far",
                "packet-trail packet-trail-near",
                "packet-head",
            ])
            self.assertEqual(len({route for _, route in paths}), 1)
            route = paths[0][1]
            if route.startswith("M0 "):
                topology["left"] += 1
            elif route.startswith("M1600 "):
                topology["right"] += 1
            elif re.match(r"M\d+ 0(?:v|l)", route):
                topology["top"] += 1
            elif re.match(r"M\d+ 900(?:v|l)", route):
                topology["bottom"] += 1
            else:
                self.fail(f"packet route does not enter from a stage edge: {route}")
        self.assertEqual(sum(topology.values()), 14)
        self.assertTrue(all(count >= 2 for count in topology.values()), topology)
        for marker in (
            "stroke-dasharray:18 82;stroke-dashoffset:118",
            "stroke-dasharray:9.5 90.5;stroke-dashoffset:109.5",
            ".packet-head{stroke:#e3ffff",
            "stroke-dasharray:.8 99.2;stroke-dashoffset:100",
            "--packet-head-opacity:.72",
            "drop-shadow(0 0 3px #e3ffff) drop-shadow(0 0 8px currentColor)",
        ):
            self.assertIn(marker, self.css)

    def test_trusted_state_mapping_is_explicit_bounded_and_fail_closed(self):
        mapping = self.js[
            self.js.index("function circuitPresentationMode"):
            self.js.index("function processingSoundMode")
        ]
        for marker in (
            'return "warning"',
            '["idle","listening","speaking","completed","warning","failed"]',
            'return "glm"', 'return "qwen"',
            'return snapshot.system_state', 'return "idle"',
        ):
            self.assertIn(marker, mapping)
        self.assertIn("document.body.dataset.circuitMode=circuitPresentationMode(s)",
                      self.js)
        lowered = mapping.lower()
        for forbidden in ("token", "throughput", "confidence", "percent",
                          "requestanimationframe", "setinterval", "settimeout"):
            self.assertNotIn(forbidden, lowered)
        self.assertNotIn("createElementNS", mapping)

    def test_qwen_runs_all_routes_forward_with_fast_unique_phases(self):
        durations = {
            int(number): float(seconds)
            for number, seconds in re.findall(
                r'body\[data-circuit-mode="qwen"\] \.packet-(\d+)'
                r'\{--packet-duration:([.\d]+)s', self.css)
        }
        self.assertEqual(set(durations), set(range(1, 15)))
        self.assertTrue(all(1.35 <= value <= 2.35 for value in durations.values()))
        qwen_start = self.css.index('body[data-circuit-mode="qwen"] .circuit-packet')
        qwen = self.css[
            qwen_start:self.css.index('body[data-active-agent="qwen"]', qwen_start)
        ]
        self.assertIn("--packet-opacity:.96;--packet-play:running", qwen)
        self.assertNotIn("reverse", qwen)
        for layer in ("far", "near", "head"):
            self.assertIn(f"animation-name:circuit-packet-forward-{layer}", self.css)
        phases = {
            int(number): float(seconds)
            for number, seconds in re.findall(
                r'\.packet-(\d+)\{--packet-delay:([-\d.]+)s\}', self.css)
        }
        self.assertEqual(set(phases), set(range(1, 15)))
        self.assertEqual(len(set(phases.values())), 14)
        self.assertTrue(all(value < 0 for value in phases.values()))

    def test_glm_runs_exactly_nine_selected_routes_in_reverse(self):
        selected_rule = re.search(
            r'((?:body\[data-circuit-mode="glm"\] \.packet-\d+,?)+)'
            r'\{--packet-opacity:\.92;--packet-play:running\}', self.css)
        self.assertIsNotNone(selected_rule)
        selected = {int(value) for value in
                    re.findall(r'\.packet-(\d+)', selected_rule.group(1))}
        self.assertEqual(len(selected), 9)
        durations = {
            int(number): float(seconds)
            for number, seconds in re.findall(
                r'body\[data-circuit-mode="glm"\] \.packet-(\d+)'
                r'\{--packet-duration:([.\d]+)s', self.css)
        }
        self.assertEqual(set(durations), selected)
        self.assertTrue(all(1.62 <= value <= 2.35 for value in durations.values()))
        for marker in (
            'body[data-circuit-mode="glm"] .circuit-packet{',
            'body[data-circuit-mode="glm"] .packet-trail-far{stroke-dashoffset:-.8;animation-name:circuit-packet-reverse-far}',
            'body[data-circuit-mode="glm"] .packet-trail-near{stroke-dashoffset:-.8;animation-name:circuit-packet-reverse-near}',
            'body[data-circuit-mode="glm"] .packet-head{stroke-dashoffset:0;animation-name:circuit-packet-reverse-head}',
            "@keyframes circuit-packet-reverse-head{from{stroke-dashoffset:0}to{stroke-dashoffset:100}}",
        ):
            self.assertIn(marker, self.css)

    def test_quiet_modes_use_sparse_forward_travel_with_long_dwell(self):
        expected_modes = {"idle", "listening", "speaking", "completed",
                          "warning", "failed"}
        for layer in ("far", "near", "head"):
            rule = re.search(
                rf'body:is\(([^)]+)\) \.packet-'
                rf'{"head" if layer == "head" else "trail-" + layer}'
                rf'\{{animation-name:circuit-packet-sparse-forward-{layer}\}}',
                self.css)
            self.assertIsNotNone(rule, layer)
            self.assertEqual(
                set(re.findall(r'data-circuit-mode="([^"]+)"', rule.group(1))),
                expected_modes)
            keyframes = re.search(
                rf'@keyframes circuit-packet-sparse-forward-{layer}'
                r'\{0%\{[^}]*opacity:0\}1%\{[^}]+\}'
                r'(\d+)%\{[^}]+\}(\d+)%,100%\{[^}]*opacity:0\}\}',
                self.css)
            self.assertIsNotNone(keyframes, layer)
            travel_complete, dwell_start = map(int, keyframes.groups())
            self.assertLessEqual(travel_complete, 25)
            self.assertGreater(dwell_start, travel_complete)
            self.assertLessEqual(dwell_start, 30)

    def test_reduced_motion_hides_only_traveling_packets(self):
        reduced_rules = re.findall(
            r"@media\(prefers-reduced-motion:reduce\)\{[^\n]+",
            self.css)
        self.assertTrue(any(".circuit-packet{display:none!important}" in rule
                            for rule in reduced_rules))
        self.assertIn('class="circuit-layer circuit-primary"', self.html)
        self.assertIn('class="circuit-layer circuit-detail"', self.html)

    def test_thinking_pulse_preserves_approved_one_shot_circuit_motion(self):
        selector_start = self.css.index(
            '.circuit-packet[data-thinking-pulse-active="true"]')
        keyframe_start = self.css.index(
            "@keyframes thinking-pulse-forward-far", selector_start)
        selector_block = self.css[selector_start:keyframe_start]
        for marker in (
            "animation-duration:var(--thinking-pulse-duration)!important",
            "animation-delay:0s!important",
            "animation-iteration-count:1!important",
            "animation-timing-function:linear!important",
            "animation-fill-mode:both!important",
            "animation-play-state:running!important",
            '[data-thinking-pulse-direction="forward"] .packet-trail-far{animation-name:thinking-pulse-forward-far!important}',
            '[data-thinking-pulse-direction="forward"] .packet-trail-near{animation-name:thinking-pulse-forward-near!important}',
            '[data-thinking-pulse-direction="forward"] .packet-head{animation-name:thinking-pulse-forward-head!important}',
            '[data-thinking-pulse-direction="reverse"] .packet-trail-far{animation-name:thinking-pulse-reverse-far!important}',
            '[data-thinking-pulse-direction="reverse"] .packet-trail-near{animation-name:thinking-pulse-reverse-near!important}',
            '[data-thinking-pulse-direction="reverse"] .packet-head{animation-name:thinking-pulse-reverse-head!important}',
        ):
            self.assertIn(marker, selector_block)
        self.assertNotIn("animation-iteration-count:infinite", selector_block)

        keyframes = self.css[keyframe_start:]
        for marker in (
            "@keyframes thinking-pulse-forward-far{0%{stroke-dashoffset:118;opacity:0}3%{stroke-dashoffset:115;opacity:var(--thinking-pulse-far-opacity)}88%{stroke-dashoffset:30;opacity:var(--thinking-pulse-far-opacity)}100%{stroke-dashoffset:18;opacity:0}}",
            "@keyframes thinking-pulse-forward-near{0%{stroke-dashoffset:109.5;opacity:0}3%{stroke-dashoffset:106.5;opacity:var(--thinking-pulse-near-opacity)}88%{stroke-dashoffset:21.5;opacity:var(--thinking-pulse-near-opacity)}100%{stroke-dashoffset:9.5;opacity:0}}",
            "@keyframes thinking-pulse-forward-head{0%{stroke-dashoffset:100;opacity:0}3%{stroke-dashoffset:97;opacity:var(--thinking-pulse-head-opacity)}88%{stroke-dashoffset:12;opacity:var(--thinking-pulse-head-opacity)}100%{stroke-dashoffset:0;opacity:0}}",
            "@keyframes thinking-pulse-reverse-far{0%{stroke-dashoffset:-.8;opacity:0}3%{stroke-dashoffset:2.2;opacity:var(--thinking-pulse-far-opacity)}88%{stroke-dashoffset:87.2;opacity:var(--thinking-pulse-far-opacity)}100%{stroke-dashoffset:99.2;opacity:0}}",
            "@keyframes thinking-pulse-reverse-near{0%{stroke-dashoffset:-.8;opacity:0}3%{stroke-dashoffset:2.2;opacity:var(--thinking-pulse-near-opacity)}88%{stroke-dashoffset:87.2;opacity:var(--thinking-pulse-near-opacity)}100%{stroke-dashoffset:99.2;opacity:0}}",
            "@keyframes thinking-pulse-reverse-head{0%{stroke-dashoffset:0;opacity:0}3%{stroke-dashoffset:3;opacity:var(--thinking-pulse-head-opacity)}88%{stroke-dashoffset:88;opacity:var(--thinking-pulse-head-opacity)}100%{stroke-dashoffset:100;opacity:0}}",
        ):
            self.assertIn(marker, keyframes)


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
