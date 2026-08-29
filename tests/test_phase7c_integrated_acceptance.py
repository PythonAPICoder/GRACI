"""Phase 7C integrated production-composition and closure acceptance."""

import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from graci.__main__ import main
from graci.keyboard_input import KeyEvent, VK_SPACE
from graci.operator_cli import MAX_CLI_ERROR, build_operator_coordinator
from graci.playback import PlaybackResult, PlaybackStatus
from graci.speech import CapturedAudio, TranscriptionResult, TranscriptionStatus
from graci.tts import SynthesizedAudio, TTSResult, TTSStatus
from graci.turn_coordinator import ExplicitTurnCoordinator
from graci.visualizer import SystemState


class Runtime:
    def __init__(self, status="PASS", error=None):
        self.calls = []
        self.status = status
        self.error = error

    def run(self, task):
        self.calls.append(task)
        if self.error is not None:
            raise self.error
        return {
            "schema_version": 1,
            "run_id": "phase7c-fixed-run",
            "status": self.status,
            "http_status": 200,
            "provider_response_model": "qwen3.8-27b-q4_k_m",
            "validated_model_result": {
                "schema_version": 2,
                "status": self.status,
                "summary": "GRACI 3090 4090 complete.",
                "user_response": ("GRACI 3090 4090 complete."
                                  if self.status == "PASS" else None),
            },
            "errors": [] if self.status == "PASS" else ["governed failure"],
            "submitted_task": task,
            "secret": "must not cross the CLI boundary",
        }


class Observer:
    def __init__(self, fail=False):
        self.states = []
        self.fail = fail

    def publish(self, event):
        self.states.append(event.state)
        if self.fail:
            raise RuntimeError("observer unavailable")


class Session:
    def stop(self):
        return CapturedAudio(b"\0\0" * 2400, 16000, 1, 2)

    def cancel(self):
        pass


class Capture:
    def __init__(self):
        self.starts = 0

    def start(self, config):
        self.starts += 1
        return Session()


class STT:
    identity = "fake-local-stt"

    def __init__(self, result=None):
        self.calls = 0
        self.result = result or TranscriptionResult(
            TranscriptionStatus.SUCCESS, self.identity, 0.15, text="exact spoken task")

    def transcribe(self, audio):
        self.calls += 1
        return self.result


class TTS:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def synthesize(self, request):
        self.calls.append(request)
        if self.fail:
            return TTSResult(TTSStatus.FAILED, "kokoro", "af_bella",
                             request.authoritative_response.text,
                             error_code="tts_failed", error_message="synthesis failed")
        return TTSResult(
            TTSStatus.SUCCESS, "kokoro", "af_bella",
            request.authoritative_response.text,
            "GRAY-see thirty ninety forty ninety complete.",
            SynthesizedAudio(b"RIFFphase7c", 24000, 1, 2, 0.5),
        )

    def cancel(self):
        pass


class Player:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def play(self, audio):
        self.calls.append(audio)
        if self.fail:
            return PlaybackResult(PlaybackStatus.FAILED, "playback_failed", "device failed")
        return PlaybackResult(PlaybackStatus.SUCCESS)

    def stop(self):
        pass


class Keyboard:
    def __init__(self):
        self.events = iter((KeyEvent(VK_SPACE, True), KeyEvent(VK_SPACE, False)))

    def next_event(self):
        return next(self.events)


class Phase7CIntegratedAcceptanceTests(unittest.TestCase):
    def test_production_stt_uses_qualified_hugging_face_cache(self):
        repository_root = Path("qualified-root")
        with patch("graci.operator_cli.FasterWhisperSubprocessSTT") as stt_constructor:
            build_operator_coordinator(repository_root)
        config = stt_constructor.call_args.args[0]
        self.assertEqual(config.model_cache,
                         repository_root / "phase6a" / "cache" / "huggingface")
        self.assertEqual((config.model, config.device, config.compute_type),
                         ("small.en", "cpu", "int8"))

    def production(self, runtime=None, *, capture=None, stt=None, tts=None,
                   player=None, observer=None):
        runtime = runtime or Runtime()
        capture = capture or Capture()
        stt = stt or STT()
        tts = tts or TTS()
        player = player or Player()
        with patch("graci.operator_cli.Controller", return_value=runtime), \
             patch("graci.operator_cli.WindowsWaveInCapture", return_value=capture), \
             patch("graci.operator_cli.FasterWhisperSubprocessSTT", return_value=stt), \
             patch("graci.operator_cli.KokoroSubprocessTTS", return_value=tts), \
             patch("graci.operator_cli.SubprocessWavePlayback", return_value=player), \
             patch("graci.operator_cli.VoiceLifecycle", wraps=(
                 lambda: __import__("graci.voice_lifecycle", fromlist=["VoiceLifecycle"])
                 .VoiceLifecycle(observer))):
            coordinator = build_operator_coordinator()
        self.assertIsInstance(coordinator, ExplicitTurnCoordinator)
        return coordinator, runtime, capture, stt, tts, player

    def invoke(self, argv, coordinator, inputs=()):
        prompts = []
        values = iter(inputs)

        def input_fn(prompt):
            prompts.append(prompt)
            return next(values)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(argv, coordinator_factory=lambda: coordinator, input_fn=input_fn,
                        keyboard_factory=Keyboard, prompt_fn=prompts.append)
        return code, json.loads(output.getvalue()), prompts

    def test_production_typed_path_is_exactly_once_and_voice_inert_by_default(self):
        coordinator, runtime, capture, stt, tts, player = self.production()
        code, payload, prompts = self.invoke([" exact typed task "], coordinator)
        self.assertEqual(code, 0)
        self.assertEqual(runtime.calls, [" exact typed task "])
        self.assertEqual(prompts, [])
        self.assertEqual((capture.starts, stt.calls, len(tts.calls), len(player.calls)),
                         (0, 0, 0, 0))
        self.assertEqual(payload["terminal_disposition"], "governed_pass")
        self.assertNotIn("secret", payload["governed"]["result"])

    def test_rejected_typed_input_is_zero_submission(self):
        coordinator, runtime, *_ = self.production()
        code, payload, _ = self.invoke([" \t"], coordinator)
        self.assertEqual(code, 1)
        self.assertEqual(runtime.calls, [])
        self.assertFalse(payload["governed"]["submitted"])

    def test_production_speech_path_requires_two_actions_and_never_reopens(self):
        coordinator, runtime, capture, stt, tts, player = self.production()
        code, payload, prompts = self.invoke(["--speech"], coordinator)
        self.assertEqual(code, 0)
        self.assertEqual(prompts,
                         ["Hold Spacebar to talk; release Spacebar to stop and transcribe."])
        self.assertEqual((capture.starts, stt.calls), (1, 1))
        self.assertEqual(runtime.calls, ["exact spoken task"])
        self.assertEqual((len(tts.calls), len(player.calls)), (0, 0))
        self.assertEqual(payload["input"]["transcription"]["text"], "exact spoken task")

    def test_failed_and_blank_speech_are_zero_submission(self):
        results = (
            TranscriptionResult(TranscriptionStatus.FAILED, "fake", 0.15,
                                error_code="no_speech", error_message="none"),
            TranscriptionResult(TranscriptionStatus.SUCCESS, "fake", 0.15, text="  "),
        )
        for result in results:
            with self.subTest(result=result):
                coordinator, runtime, capture, stt, *_ = self.production(stt=STT(result))
                code, payload, _ = self.invoke(["--speech"], coordinator)
                self.assertEqual(code, 1)
                self.assertEqual(runtime.calls, [])
                self.assertEqual((capture.starts, stt.calls), (1, 1))
                self.assertFalse(payload["governed"]["submitted"])

    def test_explicit_speak_uses_authoritative_response_and_pronunciation_copy(self):
        coordinator, runtime, _, _, tts, player = self.production()
        code, payload, _ = self.invoke(["task", "--speak"], coordinator)
        self.assertEqual(code, 0)
        self.assertEqual(runtime.calls, ["task"])
        self.assertEqual(len(tts.calls), 1)
        self.assertEqual(tts.calls[0].authoritative_response.text,
                         payload["final_response"]["text"])
        self.assertEqual(len(player.calls), 1)
        self.assertEqual(payload["presentation"]["status"], "spoken")

    def test_presentation_failures_and_observer_failures_preserve_governed_truth(self):
        for tts, player in ((TTS(fail=True), Player()), (TTS(), Player(fail=True))):
            with self.subTest(tts=tts, player=player):
                observer = Observer(fail=True)
                coordinator, runtime, _, _, _, _ = self.production(
                    tts=tts, player=player, observer=observer)
                code, payload, _ = self.invoke(["task", "--speak"], coordinator)
                self.assertEqual(code, 0)
                self.assertEqual(runtime.calls, ["task"])
                self.assertEqual(payload["governed"]["outcome"], "PASS")
                self.assertEqual(payload["presentation"]["status"], "failed")

    def test_integrated_lifecycle_is_bounded_observer_only_and_returns_idle(self):
        observer = Observer(fail=True)
        coordinator, runtime, *_ = self.production(observer=observer)
        code, payload, _ = self.invoke(["--speech", "--speak"], coordinator)
        self.assertEqual(code, 0)
        self.assertEqual(runtime.calls, ["exact spoken task"])
        self.assertEqual(observer.states, [SystemState.LISTENING, SystemState.IDLE,
                                           SystemState.SPEAKING, SystemState.IDLE])
        self.assertEqual(payload["governed"]["outcome"], "PASS")

    def test_governed_fail_and_exception_are_truthful_bounded_and_never_retried(self):
        cases = (Runtime("FAIL"), Runtime(error=RuntimeError("x" * 1000)))
        for runtime in cases:
            with self.subTest(runtime=runtime):
                coordinator, *_ = self.production(runtime)
                code, payload, _ = self.invoke(["task"], coordinator)
                self.assertEqual(code, 1)
                self.assertEqual(runtime.calls, ["task"])
                if payload["error"] is not None:
                    self.assertLessEqual(len(payload["error"]["message"]), MAX_CLI_ERROR)

    def test_workspace_target_is_distinct_and_cannot_enter_voice(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["task", "--workspace", "safe", "--target", "file.txt", "--speech"],
                 coordinator_factory=lambda: self.fail("ordinary path entered"))


if __name__ == "__main__":
    unittest.main()
