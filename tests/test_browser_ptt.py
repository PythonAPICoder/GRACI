"""Focused resident browser PTT behavior, transport, and UI safety tests."""

import http.client
import io
import json
import struct
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace

from graci.browser_ptt import (MAX_BROWSER_AUDIO_BYTES, BrowserPTTBusy,
                               BrowserPTTInvalid, BrowserPTTOperator)
from graci.speech import TranscriptionResult, TranscriptionStatus
from graci.playback import PlaybackResult, PlaybackStatus
from graci.speech_presentation import PresentationStatus, SpeechPresentationService
from graci.tts import AuthoritativeFinalResponse
from graci.tts import SynthesizedAudio, TTSResult, TTSStatus
from graci.turn_coordinator import ExplicitTurnCoordinator
from graci.visualizer import SystemState
from graci.visualizer_backend import BASE_PATH, VisualizerServer, VisualizerStateProvider
from graci.voice_lifecycle import VoiceLifecycle


ROOT = Path(__file__).parents[1]
UI = ROOT / "graci" / "visualizer_ui"


def wav_bytes(seconds=.2, rate=16_000):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate)
        wav.writeframes(struct.pack("<h", 100) * int(seconds * rate))
    return output.getvalue()


class STT:
    identity = "faster-whisper:small.en:cpu-int8"

    def __init__(self, result=None, failure=None):
        self.result = result or TranscriptionResult(
            TranscriptionStatus.SUCCESS, self.identity, .2, "hello GRACI")
        self.failure = failure
        self.calls = []

    def transcribe(self, audio):
        self.calls.append(audio)
        if self.failure:
            raise self.failure
        return self.result


class Coordinator:
    def __init__(self, response="Validated answer"):
        self.calls = []
        self.speech_requests = []
        self.response = response

    def run_typed(self, text, *, present_speech=False):
        self.calls.append(text)
        self.speech_requests.append(present_speech)
        authoritative = (AuthoritativeFinalResponse(self.response)
                         if self.response is not None else None)
        return SimpleNamespace(authoritative_response=authoritative)


class BrowserOperatorTests(unittest.TestCase):
    def make(self, stt=None, coordinator=None):
        lifecycle = VoiceLifecycle()
        return (BrowserPTTOperator(stt or STT(), coordinator or Coordinator(), lifecycle),
                lifecycle)

    def test_valid_audio_uses_existing_stt_then_exactly_one_coordinator_run(self):
        stt, coordinator = STT(), Coordinator()
        operator, lifecycle = self.make(stt, coordinator)
        token = operator.begin()
        self.assertEqual(lifecycle.state, SystemState.LISTENING)
        result = operator.finish(token, wav_bytes())
        self.assertEqual(lifecycle.state, SystemState.IDLE)
        self.assertEqual((len(stt.calls), coordinator.calls), (1, ["hello GRACI"]))
        self.assertEqual(coordinator.speech_requests, [True])
        self.assertEqual(result.turn_result.authoritative_response.text, "Validated answer")
        with self.assertRaises(BrowserPTTInvalid):
            operator.finish(token, wav_bytes())
        self.assertEqual(len(coordinator.calls), 1)


class GovernedRuntime:
    def __init__(self): self.calls = []
    def run(self, task):
        self.calls.append(task)
        return {"status":"PASS", "validated_model_result": {
            "schema_version":2, "status":"PASS", "summary":"internal",
            "user_response":"GRACI completed the browser voice turn."}}


class FinalConstructor:
    def __init__(self): self.calls = []
    def construct(self, governed):
        self.calls.append(governed)
        return AuthoritativeFinalResponse(
            governed["validated_model_result"]["user_response"])


class PresentationTTS:
    def __init__(self, fail=False): self.calls = []; self.fail = fail
    def synthesize(self, request):
        self.calls.append(request)
        if self.fail:
            return TTSResult(TTSStatus.FAILED, "Kokoro-82M-ONNX:cpu", "af_bella",
                             request.authoritative_response.text,
                             error_code="tts_failed", error_message="synthetic failure")
        audio = SynthesizedAudio(b"RIFFbrowser-ptt", 24_000, 1, 2, .25)
        return TTSResult(TTSStatus.SUCCESS, "Kokoro-82M-ONNX:cpu", "af_bella",
                         request.authoritative_response.text,
                         "GRAY-see completed the browser voice turn.", audio)
    def cancel(self): pass


class PresentationPlayer:
    def __init__(self, lifecycle): self.calls = []; self.states = []; self.lifecycle = lifecycle
    def play(self, audio):
        self.calls.append(audio); self.states.append(self.lifecycle.state)
        return PlaybackResult(PlaybackStatus.SUCCESS)
    def stop(self): pass


class LifecycleObserver:
    def __init__(self): self.states = []
    def publish(self, event): self.states.append(event.state)


class BrowserPresentationIntegrationTests(unittest.TestCase):
    def make(self, stt=None, coordinator=None):
        lifecycle = VoiceLifecycle()
        return (BrowserPTTOperator(stt or STT(), coordinator or Coordinator(), lifecycle),
                lifecycle)

    def composition(self, *, tts_fail=False):
        observer = LifecycleObserver(); lifecycle = VoiceLifecycle(observer)
        runtime, constructor = GovernedRuntime(), FinalConstructor()
        tts, player = PresentationTTS(tts_fail), PresentationPlayer(lifecycle)
        coordinator = ExplicitTurnCoordinator(
            runtime, final_response_constructor=constructor,
            speech_presentation=SpeechPresentationService(tts, player, lifecycle))
        operator = BrowserPTTOperator(STT(), coordinator, lifecycle)
        return operator, runtime, constructor, tts, player, observer, lifecycle

    def test_browser_ptt_speaks_once_from_same_authoritative_response(self):
        operator, runtime, constructor, tts, player, observer, lifecycle = self.composition()
        result = operator.finish(operator.begin(), wav_bytes())
        response = result.turn_result.authoritative_response
        presentation = result.turn_result.speech_presentation
        self.assertEqual(runtime.calls, ["hello GRACI"])
        self.assertEqual(len(constructor.calls), 1)
        self.assertEqual((len(tts.calls), len(player.calls)), (1, 1))
        self.assertIs(tts.calls[0].authoritative_response, response)
        self.assertIs(presentation.authoritative_response, response)
        self.assertEqual(presentation.status, PresentationStatus.SPOKEN)
        self.assertEqual(player.states, [SystemState.SPEAKING])
        self.assertEqual(observer.states, [SystemState.LISTENING, SystemState.IDLE,
                                           SystemState.SPEAKING, SystemState.IDLE])
        self.assertEqual(lifecycle.state, SystemState.IDLE)

    def test_tts_failure_preserves_text_success_and_never_reruns(self):
        operator, runtime, constructor, tts, player, observer, lifecycle = self.composition(
            tts_fail=True)
        result = operator.finish(operator.begin(), wav_bytes())
        self.assertEqual(runtime.calls, ["hello GRACI"])
        self.assertEqual((len(constructor.calls), len(tts.calls), len(player.calls)), (1, 1, 0))
        self.assertEqual(result.turn_result.authoritative_response.text,
                         "GRACI completed the browser voice turn.")
        self.assertEqual(result.turn_result.speech_presentation.status,
                         PresentationStatus.FAILED)
        self.assertEqual(observer.states, [SystemState.LISTENING, SystemState.IDLE])
        self.assertEqual(lifecycle.state, SystemState.IDLE)

    def test_blank_transcript_and_stt_failure_cause_zero_runs(self):
        cases = (
            STT(TranscriptionResult(TranscriptionStatus.SUCCESS, "local", .2, "   ")),
            STT(failure=RuntimeError("offline failure")),
            STT(TranscriptionResult(TranscriptionStatus.FAILED, "local", .2,
                                    error_code="worker_failed", error_message="failed")),
        )
        for stt in cases:
            with self.subTest(stt=stt.result.status):
                coordinator = Coordinator(); operator, _ = self.make(stt, coordinator)
                result = operator.finish(operator.begin(), wav_bytes())
                self.assertEqual(coordinator.calls, [])
                self.assertIsNone(result.turn_result)

    def test_duplicate_active_cancel_and_invalid_audio_fail_closed(self):
        coordinator = Coordinator(); operator, lifecycle = self.make(coordinator=coordinator)
        token = operator.begin()
        with self.assertRaises(BrowserPTTBusy): operator.begin()
        operator.cancel(token)
        self.assertEqual(lifecycle.state, SystemState.IDLE)
        self.assertEqual(coordinator.calls, [])
        for invalid in (b"", b"not wave", b"x" * (MAX_BROWSER_AUDIO_BYTES + 1),
                        wav_bytes(.1), wav_bytes(120.1, 8_000)):
            with self.subTest(size=len(invalid)):
                result = operator.finish(operator.begin(), invalid)
                self.assertIsNone(result.turn_result)
        self.assertEqual(coordinator.calls, [])


class BrowserTransportTests(unittest.TestCase):
    def setUp(self):
        self.coordinator = Coordinator("Only validated user-facing text")
        self.operator = BrowserPTTOperator(STT(), self.coordinator, VoiceLifecycle())
        self.server = VisualizerServer(VisualizerStateProvider(), port=0,
                                       browser_ptt=self.operator)
        self.server.start()

    def tearDown(self):
        self.operator.close(); self.server.stop()

    def request(self, path, body, content_type, token=None, extra=None):
        headers = {"Host": f"127.0.0.1:{self.server.bound_port}",
                   "Content-Type": content_type}
        if token: headers["X-GRACI-PTT-Token"] = token
        if extra: headers.update(extra)
        connection = http.client.HTTPConnection("127.0.0.1", self.server.bound_port, timeout=2)
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse(); payload = response.read()
        result = response.status, dict(response.getheaders()), payload
        connection.close(); return result

    def begin(self):
        status, _, body = self.request(f"{BASE_PATH}/ptt/begin", b"{}", "application/json")
        self.assertEqual(status, 200)
        return json.loads(body)["turn_token"]

    def test_strict_same_origin_content_type_size_and_inflight_validation(self):
        self.assertEqual(self.request(f"{BASE_PATH}/ptt/begin", b"{}", "text/plain")[0], 415)
        self.assertEqual(self.request(f"{BASE_PATH}/ptt/begin", b'{"task":"x"}', "application/json")[0], 400)
        self.assertEqual(self.request(f"{BASE_PATH}/ptt/begin", b"{}", "application/json",
                                      extra={"Origin":"http://evil.test"})[0], 403)
        token = self.begin()
        self.assertEqual(self.request(f"{BASE_PATH}/ptt/begin", b"{}", "application/json")[0], 409)
        self.assertEqual(self.request(f"{BASE_PATH}/ptt/finish", b"bad", "audio/wav", token)[0], 422)
        self.assertEqual(self.coordinator.calls, [])

    def test_success_response_exposes_only_validated_result_and_cannot_replay(self):
        token = self.begin()
        status, _, body = self.request(f"{BASE_PATH}/ptt/finish", wav_bytes(), "audio/wav", token)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status":"ok", "response":"Only validated user-facing text"})
        rendered = body.decode()
        for secret in ("transcript", "provider", "reasoning", "reviewer", "implementation"):
            self.assertNotIn(secret, rendered.lower())
        self.assertEqual(self.request(f"{BASE_PATH}/ptt/finish", wav_bytes(), "audio/wav", token)[0], 409)
        self.assertEqual(len(self.coordinator.calls), 1)


class BrowserUIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (UI / "index.html").read_text("utf-8")
        cls.js = (UI / "visualizer.js").read_text("utf-8")

    def test_explicit_control_no_startup_capture_and_permission_failure_visible(self):
        self.assertIn('id="ptt-button"', self.html)
        self.assertIn('id="operator-response"', self.html)
        self.assertIn('MICROPHONE OFF', self.html)
        self.assertIn('getUserMedia', self.js)
        self.assertLess(self.js.index('function beginPTT'), self.js.index('getUserMedia'))
        self.assertIn('MICROPHONE UNAVAILABLE', self.js)

    def test_spacebar_editable_repeat_release_and_pointer_semantics_are_guarded(self):
        for marker in ("input,textarea,select", "[contenteditable]", "event.repeat",
                       "!ptt.spaceHeld", 'event.code!=="Space"', "pointerdown",
                       "pointerup", "pointercancel", "lostpointercapture"):
            self.assertIn(marker, self.js)
        self.assertIn('if(event.code!=="Space"||!ptt.spaceHeld)return', self.js)
        self.assertIn('if(ptt.phase!=="idle")return', self.js)

    def test_interruption_reload_and_capture_are_cancel_only(self):
        for marker in ('window.addEventListener("blur"', '"visibilitychange"',
                       '"pagehide"', 'track.stop()', '"/ptt/cancel"'):
            self.assertIn(marker, self.js)
        self.assertNotIn("localStorage", self.js)
        self.assertNotIn("sessionStorage", self.js)


if __name__ == "__main__": unittest.main()
