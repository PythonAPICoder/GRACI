"""Focused Phase 7B local operator CLI integration acceptance."""

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from graci.__main__ import main
from graci.operator_cli import serialize_turn_result
from graci.playback import PlaybackResult, PlaybackStatus
from graci.speech import TranscriptionResult, TranscriptionStatus
from graci.speech_presentation import SpeechPresentationService
from graci.tts import AuthoritativeFinalResponse, TTSResult, TTSStatus
from graci.turn_coordinator import ExplicitTurnCoordinator


class Runtime:
    def __init__(self, status="PASS", error=None):
        self.calls = []
        self.error = error
        self.result = {
            "schema_version": 1, "run_id": "fixed-run", "status": status,
            "http_status": 200, "provider_response_model": "local-model",
            "validated_model_result": {"schema_version": 1, "status": status,
                                       "summary": "GRACI finished."},
            "errors": [] if status == "PASS" else ["bounded failure"],
            "submitted_task": "must not be projected",
            "execution": {"endpoint": "must not be projected"},
        }

    def run(self, task):
        self.calls.append(task)
        if self.error:
            raise self.error
        return self.result


class PushToTalk:
    def __init__(self, transcription=None, begin_error=None):
        self.transcription = transcription or TranscriptionResult(
            TranscriptionStatus.SUCCESS, "fake-local-stt", 1.0, text="spoken task")
        self.begins = 0
        self.finishes = 0
        self.begin_error = begin_error

    def begin(self):
        self.begins += 1
        if self.begin_error:
            raise self.begin_error

    def end_and_transcribe(self):
        self.finishes += 1
        return self.transcription


class Constructor:
    def construct(self, governed):
        return AuthoritativeFinalResponse(governed["validated_model_result"]["summary"])


class TTS:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def synthesize(self, request):
        self.calls.append(request)
        return TTSResult(TTSStatus.FAILED, "kokoro", "af_bella",
                         request.authoritative_response.text,
                         error_code="tts_failed", error_message="bounded failure")

    def cancel(self):
        pass


class Player:
    def __init__(self):
        self.calls = []

    def play(self, audio):
        self.calls.append(audio)
        return PlaybackResult(PlaybackStatus.SUCCESS)

    def stop(self):
        pass


class Phase7BOperatorCLITests(unittest.TestCase):
    def run_cli(self, argv, coordinator, inputs=()):
        prompts = []
        values = iter(inputs)

        def input_fn(prompt):
            prompts.append(prompt)
            return next(values)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(argv, coordinator_factory=lambda: coordinator, input_fn=input_fn)
        return code, json.loads(output.getvalue()), prompts

    @staticmethod
    def coordinator(runtime, ptt=None, service=None):
        return ExplicitTurnCoordinator(runtime, push_to_talk=ptt,
                                       final_response_constructor=Constructor(),
                                       speech_presentation=service)

    def test_typed_cli_uses_coordinator_once_without_source_rewriting(self):
        runtime = Runtime()
        code, payload, prompts = self.run_cli(["exact semantic task"], self.coordinator(runtime))
        self.assertEqual(code, 0)
        self.assertEqual(runtime.calls, ["exact semantic task"])
        self.assertEqual(payload["input"]["source"], "typed")
        self.assertTrue(payload["governed"]["submitted"])
        self.assertEqual(prompts, [])

    def test_blank_typed_input_submits_zero_and_exits_nonzero(self):
        runtime = Runtime()
        code, payload, _ = self.run_cli([" \t"], self.coordinator(runtime))
        self.assertEqual(code, 1)
        self.assertEqual(runtime.calls, [])
        self.assertFalse(payload["governed"]["submitted"])
        self.assertEqual(payload["terminal_disposition"], "input_rejected")

    def test_speech_requires_explicit_start_and_stop_and_submits_at_most_once(self):
        runtime, ptt = Runtime(), PushToTalk()
        code, payload, prompts = self.run_cli(["--speech"], self.coordinator(runtime, ptt), ("", ""))
        self.assertEqual(code, 0)
        self.assertEqual((ptt.begins, ptt.finishes), (1, 1))
        self.assertEqual(len(prompts), 2)
        self.assertEqual(runtime.calls, ["spoken task"])
        self.assertEqual(payload["input"]["source"], "speech")

    def test_failed_speech_submits_zero(self):
        failed = TranscriptionResult(TranscriptionStatus.FAILED, "fake", 0.2,
                                     error_code="no_speech", error_message="none")
        runtime, ptt = Runtime(), PushToTalk(failed)
        code, payload, _ = self.run_cli(["--speech"], self.coordinator(runtime, ptt), ("", ""))
        self.assertEqual(code, 1)
        self.assertEqual(runtime.calls, [])
        self.assertFalse(payload["governed"]["submitted"])

    def test_speech_start_failure_reports_requested_presentation_truthfully(self):
        runtime, ptt = Runtime(), PushToTalk(begin_error=OSError("no microphone"))
        code, payload, _ = self.run_cli(["--speech", "--speak"],
                                        self.coordinator(runtime, ptt), ("",))
        self.assertEqual(code, 1)
        self.assertEqual(runtime.calls, [])
        self.assertTrue(payload["presentation"]["requested"])
        self.assertEqual(payload["terminal_disposition"], "input_failed")

    def test_typed_mode_never_touches_microphone(self):
        runtime, ptt = Runtime(), PushToTalk()
        self.run_cli(["task"], self.coordinator(runtime, ptt))
        self.assertEqual((ptt.begins, ptt.finishes), (0, 0))

    def test_presentation_is_opt_in(self):
        runtime, tts, player = Runtime(), TTS(), Player()
        service = SpeechPresentationService(tts, player)
        _, payload, _ = self.run_cli(["task"], self.coordinator(runtime, service=service))
        self.assertEqual(tts.calls, [])
        self.assertFalse(payload["presentation"]["requested"])

    def test_explicit_presentation_failure_preserves_pass_and_success_exit(self):
        runtime, tts, player = Runtime(), TTS(fail=True), Player()
        service = SpeechPresentationService(tts, player)
        code, payload, _ = self.run_cli(["--speak", "task"],
                                        self.coordinator(runtime, service=service))
        self.assertEqual(code, 0)
        self.assertEqual(runtime.calls, ["task"])
        self.assertEqual(len(tts.calls), 1)
        self.assertEqual(payload["governed"]["outcome"], "PASS")
        self.assertEqual(payload["presentation"]["status"], "failed")

    def test_fail_error_and_no_submission_are_nonzero(self):
        cases = (Runtime("FAIL"), Runtime(error=RuntimeError("runtime failed")))
        for runtime in cases:
            with self.subTest(runtime=runtime):
                code, _, _ = self.run_cli(["task"], self.coordinator(runtime))
                self.assertEqual(code, 1)

    def test_serialization_is_deterministic_bounded_and_allowlisted(self):
        runtime = Runtime()
        runtime.result["errors"] = ["x" * 1_000] * 30
        result = self.coordinator(runtime).run_typed("task")
        first = serialize_turn_result(result)
        second = serialize_turn_result(result)
        self.assertEqual(first, second)
        governed = first["governed"]["result"]
        self.assertNotIn("submitted_task", governed)
        self.assertNotIn("execution", governed)
        self.assertEqual(len(governed["errors"]), 20)
        self.assertTrue(all(len(item) == 500 for item in governed["errors"]))

    def test_no_cli_retry_after_runtime_error(self):
        runtime = Runtime(error=RuntimeError("once"))
        self.run_cli(["task"], self.coordinator(runtime))
        self.assertEqual(runtime.calls, ["task"])

    def test_workspace_target_remain_specialized_legacy_path(self):
        record = {"status": "PASS", "legacy": True}
        with patch("graci.__main__.VerticalSliceController") as controller:
            controller.return_value.run.return_value = record
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["task", "--workspace", "safe", "--target", "file.txt"],
                            coordinator_factory=lambda: self.fail("ordinary coordinator used"))
        self.assertEqual(code, 0)
        controller.assert_called_once_with("safe", "file.txt")
        controller.return_value.run.assert_called_once_with("task")
        self.assertEqual(json.loads(output.getvalue()), record)

    def test_invalid_mode_combination_is_rejected_before_construction(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["task", "--speech"], coordinator_factory=lambda: self.fail("constructed"))


if __name__ == "__main__":
    unittest.main()
