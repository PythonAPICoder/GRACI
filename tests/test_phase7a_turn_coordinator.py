"""Focused Phase 7A explicit turn coordinator acceptance."""

import dataclasses
import unittest

from graci.playback import PlaybackResult, PlaybackStatus
from graci.speech import TranscriptionResult, TranscriptionStatus
from graci.speech_presentation import SpeechPresentationService
from graci.tts import (AuthoritativeFinalResponse, SynthesizedAudio, TTSResult,
                       TTSStatus)
from graci.turn_coordinator import (ExplicitTurnCoordinator, InputOutcome,
                                    InputSource, TurnDisposition)
from graci.visualizer import SystemState
from graci.voice_lifecycle import VoiceLifecycle


class Runtime:
    def __init__(self, status="PASS", error=None):
        self.calls = []
        self.result = {"status": status, "opaque": "governed"}
        self.error = error

    def run(self, task):
        self.calls.append(task)
        if self.error:
            raise self.error
        return self.result


class ResponseConstructor:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def construct(self, governed):
        self.calls.append(governed)
        if self.error:
            raise self.error
        return AuthoritativeFinalResponse("GRACI completed the governed turn.")


class PushToTalk:
    def __init__(self, transcription=None, begin_error=None, finish_error=None):
        self.transcription = transcription or TranscriptionResult(
            TranscriptionStatus.SUCCESS, "fake-local-stt", 1.0, text="same semantic task")
        self.begin_error = begin_error
        self.finish_error = finish_error
        self.begins = 0
        self.finishes = 0

    def begin(self):
        self.begins += 1
        if self.begin_error:
            raise self.begin_error

    def end_and_transcribe(self):
        self.finishes += 1
        if self.finish_error:
            raise self.finish_error
        return self.transcription


class Observer:
    def __init__(self, fail=False):
        self.states = []
        self.fail = fail

    def publish(self, event):
        self.states.append(event.state)
        if self.fail:
            raise RuntimeError("observer offline")


class LifecyclePushToTalk(PushToTalk):
    def __init__(self, lifecycle, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lifecycle = lifecycle
        self.lease = None

    def begin(self):
        super().begin()
        self.lease = self.lifecycle.enter(SystemState.LISTENING)

    def end_and_transcribe(self):
        try:
            return super().end_and_transcribe()
        finally:
            self.lease.close()


def audio():
    return SynthesizedAudio(b"RIFFphase7a", 24000, 1, 2, .5)


class TTS:
    def __init__(self, lifecycle=None, fail=False):
        self.lifecycle = lifecycle
        self.fail = fail
        self.calls = []

    def synthesize(self, request):
        self.calls.append(request)
        if self.fail:
            return TTSResult(TTSStatus.FAILED, "kokoro", "af_heart",
                             request.authoritative_response.text,
                             error_code="tts_failed", error_message="failed")
        return TTSResult(TTSStatus.SUCCESS, "kokoro", "af_heart",
                         request.authoritative_response.text,
                         "GRAY-see completed the governed turn.", audio())

    def cancel(self):
        pass


class Player:
    def __init__(self, lifecycle=None, fail=False):
        self.lifecycle = lifecycle
        self.fail = fail
        self.calls = []
        self.states = []

    def play(self, value):
        self.calls.append(value)
        if self.lifecycle:
            self.states.append(self.lifecycle.state)
        if self.fail:
            return PlaybackResult(PlaybackStatus.FAILED, "playback_failed", "failed")
        return PlaybackResult(PlaybackStatus.SUCCESS)

    def stop(self):
        pass


class Phase7ATurnCoordinatorTests(unittest.TestCase):
    def coordinator(self, runtime=None, ptt=None, constructor=None, service=None):
        return ExplicitTurnCoordinator(runtime or Runtime(), push_to_talk=ptt,
                                       final_response_constructor=constructor,
                                       speech_presentation=service)

    def test_typed_and_speech_each_submit_exactly_once_without_source_rewriting(self):
        for source in (InputSource.TYPED, InputSource.SPEECH):
            runtime = Runtime()
            ptt = PushToTalk()
            coordinator = self.coordinator(runtime, ptt)
            result = (coordinator.run_typed("same semantic task")
                      if source is InputSource.TYPED else self._speech(coordinator))
            self.assertEqual(runtime.calls, ["same semantic task"])
            self.assertIs(result.input_source, source)
            self.assertTrue(result.governed_submitted)

    def test_blank_typed_input_submits_zero(self):
        runtime = Runtime()
        result = self.coordinator(runtime).run_typed(" \t\n")
        self.assertEqual(runtime.calls, [])
        self.assertIs(result.input_outcome, InputOutcome.REJECTED)
        self.assertIs(result.disposition, TurnDisposition.INPUT_REJECTED)

    def test_failed_acquisition_and_failed_or_blank_transcription_submit_zero(self):
        cases = (
            PushToTalk(begin_error=OSError("no microphone")),
            PushToTalk(finish_error=OSError("device lost")),
            PushToTalk(TranscriptionResult(TranscriptionStatus.FAILED, "stt", 1,
                                           error_code="rejected", error_message="rejected")),
            PushToTalk(TranscriptionResult(TranscriptionStatus.SUCCESS, "stt", 1, text=" ")),
            PushToTalk("not a transcription result"),
        )
        for ptt in cases:
            with self.subTest(ptt=ptt):
                runtime = Runtime()
                coordinator = self.coordinator(runtime, ptt)
                start = coordinator.begin_speech_turn()
                result = start if start is not None else coordinator.finish_speech_turn()
                self.assertFalse(result.governed_submitted)
                self.assertEqual(runtime.calls, [])

    def test_governed_pass_and_fail_remain_truthful_without_implicit_speech(self):
        for status, disposition in (("PASS", TurnDisposition.GOVERNED_PASS),
                                    ("FAIL", TurnDisposition.GOVERNED_FAIL)):
            runtime, tts, player = Runtime(status), TTS(), Player()
            service = SpeechPresentationService(tts, player)
            result = self.coordinator(runtime, constructor=ResponseConstructor(),
                                      service=service).run_typed("task")
            self.assertIs(result.governed_result, runtime.result)
            self.assertIs(result.disposition, disposition)
            self.assertFalse(result.speech_requested)
            self.assertEqual(tts.calls, [])
            self.assertEqual(player.calls, [])

    def test_optional_successful_speech_uses_explicit_authoritative_response(self):
        constructor, tts, player = ResponseConstructor(), TTS(), Player()
        result = self.coordinator(constructor=constructor,
                                  service=SpeechPresentationService(tts, player)).run_typed(
                                      "task", present_speech=True)
        self.assertEqual(len(constructor.calls), 1)
        self.assertEqual(len(tts.calls), 1)
        self.assertEqual(len(player.calls), 1)
        self.assertIs(result.speech_presentation.authoritative_response,
                      result.authoritative_response)

    def test_tts_and_playback_failures_leave_governed_result_unchanged(self):
        for tts, player in ((TTS(fail=True), Player()), (TTS(), Player(fail=True))):
            runtime = Runtime()
            result = self.coordinator(runtime, constructor=ResponseConstructor(),
                                      service=SpeechPresentationService(tts, player)).run_typed(
                                          "task", present_speech=True)
            self.assertIs(result.governed_result, runtime.result)
            self.assertEqual(result.governed_result["status"], "PASS")
            self.assertEqual(runtime.calls, ["task"])
            self.assertEqual(result.speech_presentation.status.value, "failed")

    def test_observer_failure_and_lifecycle_semantics_are_isolated(self):
        observer = Observer(fail=True)
        lifecycle = VoiceLifecycle(observer)
        ptt = LifecyclePushToTalk(lifecycle)
        player = Player(lifecycle)
        service = SpeechPresentationService(TTS(lifecycle), player, lifecycle)
        runtime = Runtime()
        coordinator = self.coordinator(runtime, ptt, ResponseConstructor(), service)
        self.assertIsNone(coordinator.begin_speech_turn())
        result = coordinator.finish_speech_turn(present_speech=True)
        self.assertIs(result.governed_result, runtime.result)
        self.assertEqual(runtime.calls, ["same semantic task"])
        self.assertEqual(observer.states, [SystemState.LISTENING, SystemState.IDLE,
                                           SystemState.SPEAKING, SystemState.IDLE])
        self.assertEqual(player.states, [SystemState.SPEAKING])
        self.assertIs(lifecycle.state, SystemState.IDLE)

    def test_turn_result_is_frozen_and_deterministic(self):
        first = self.coordinator(Runtime()).run_typed("task")
        second = self.coordinator(Runtime()).run_typed("task")
        self.assertEqual(first, second)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            first.governed_submitted = False

    def test_runtime_and_response_construction_exceptions_are_deterministic(self):
        runtime = Runtime(error=RuntimeError("runtime boundary failed"))
        result = self.coordinator(runtime).run_typed("task")
        self.assertTrue(result.governed_submitted)
        self.assertIs(result.disposition, TurnDisposition.GOVERNED_ERROR)
        self.assertIsNone(result.governed_result)
        self.assertEqual(runtime.calls, ["task"])

        runtime = Runtime()
        result = self.coordinator(
            runtime, constructor=ResponseConstructor(RuntimeError("cannot select response"))) \
            .run_typed("task", present_speech=True)
        self.assertIs(result.governed_result, runtime.result)
        self.assertIs(result.disposition, TurnDisposition.GOVERNED_PASS)
        self.assertEqual(result.error_code, "final_response_construction_failed")

    def test_exactly_once_invariant_across_all_terminal_paths(self):
        runtime = Runtime()
        coordinator = self.coordinator(runtime, PushToTalk())
        self.assertIsNone(coordinator.begin_speech_turn())
        coordinator.finish_speech_turn(present_speech=True)
        self.assertEqual(len(runtime.calls), 1)
        rejected = coordinator.finish_speech_turn()
        self.assertFalse(rejected.governed_submitted)
        self.assertEqual(len(runtime.calls), 1)

    @staticmethod
    def _speech(coordinator):
        assert coordinator.begin_speech_turn() is None
        return coordinator.finish_speech_turn()


if __name__ == "__main__":
    unittest.main()
