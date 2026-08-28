"""Integrated deterministic acceptance and closure for the accepted Phase 6 boundary."""

import json
import unittest
from pathlib import Path

from phase6a.pronunciation import speech_presentation_text
from graci.audio_capture import AudioCaptureConfig
from graci.playback import PlaybackResult, PlaybackStatus
from graci.push_to_talk import PushToTalkController
from graci.speech import CapturedAudio, TranscriptionResult, TranscriptionStatus
from graci.speech_presentation import PresentationStatus, SpeechPresentationService
from graci.speech_runtime import SpeechRuntimeAdapter, TranscriptSubmissionError
from graci.tts import (AuthoritativeFinalResponse, SynthesizedAudio, TTSRequest,
                       TTSResult, TTSStatus)
from graci.visualizer import SystemState
from graci.voice_lifecycle import VoiceLifecycle


class Observer:
    def __init__(self, fail_states=()):
        self.events = []
        self.fail_states = frozenset(fail_states)

    def publish(self, event):
        self.events.append(event)
        if event.state in self.fail_states:
            raise RuntimeError(f"publisher failed for {event.state.value}")


class Session:
    def __init__(self, stop_error=None, cancel_error=None):
        self.stop_error = stop_error
        self.cancel_error = cancel_error
        self.cancelled = False

    def stop(self):
        if self.stop_error:
            raise self.stop_error
        return CapturedAudio(b"\0\0" * 16000, 16000, 1, 2)

    def cancel(self):
        self.cancelled = True
        if self.cancel_error:
            raise self.cancel_error


class Capture:
    def __init__(self, session=None):
        self.session = session or Session()
        self.starts = 0

    def start(self, config):
        self.starts += 1
        return self.session


class STT:
    identity = "closure-fake-stt"

    def __init__(self, result=None, error=None, lifecycle=None):
        self.result = result or TranscriptionResult(
            TranscriptionStatus.SUCCESS, self.identity, 1.0,
            text="  Ask GRACI exactly once?!  ")
        self.error = error
        self.lifecycle = lifecycle
        self.calls = 0

    def transcribe(self, audio):
        self.calls += 1
        if self.lifecycle is not None:
            assert self.lifecycle.state is SystemState.LISTENING
        if self.error:
            raise self.error
        return self.result


class Runtime:
    def __init__(self):
        self.calls = []
        self.result = {"status": "PASS", "opaque": "completed-governed-result"}

    def run(self, task):
        self.calls.append(task)
        return self.result


def bounded_audio():
    return SynthesizedAudio(b"RIFFclosure", 24000, 1, 2, 0.5)


class Synthesizer:
    def __init__(self, lifecycle, status=TTSStatus.SUCCESS):
        self.lifecycle = lifecycle
        self.status = status
        self.requests = []
        self.cancelled = False
        self.state_during_synthesis = None

    def synthesize(self, request):
        self.requests.append(request)
        self.state_during_synthesis = self.lifecycle.state
        text = request.authoritative_response.text
        spoken = speech_presentation_text(text)
        if self.status is not TTSStatus.SUCCESS:
            return TTSResult(self.status, "closure-fake-tts", "af_bella", text,
                             spoken, error_code="tts_failed", error_message="failed")
        return TTSResult(self.status, "closure-fake-tts", "af_bella", text,
                         spoken, bounded_audio())

    def cancel(self):
        self.cancelled = True


class Player:
    def __init__(self, lifecycle, result=None, cancel_during_play=False):
        self.lifecycle = lifecycle
        self.result = result or PlaybackResult(PlaybackStatus.SUCCESS)
        self.cancel_during_play = cancel_during_play
        self.calls = []
        self.stopped = False
        self.state_during_playback = None

    def play(self, audio):
        self.calls.append(audio)
        self.state_during_playback = self.lifecycle.state
        if self.cancel_during_play:
            self.stop()
            return PlaybackResult(PlaybackStatus.CANCELLED, "playback_cancelled",
                                  "explicit cancellation")
        return self.result

    def stop(self):
        self.stopped = True


class Phase6IntegratedClosureTests(unittest.TestCase):
    def listen(self, lifecycle, stt=None, session=None):
        stt = stt or STT(lifecycle=lifecycle)
        controller = PushToTalkController(Capture(session), stt,
                                          AudioCaptureConfig(), lifecycle)
        controller.begin()
        return controller, stt, controller.end_and_transcribe()

    def present(self, lifecycle, response, *, tts_status=TTSStatus.SUCCESS,
                playback=None, cancel_during_play=False):
        synthesizer = Synthesizer(lifecycle, tts_status)
        player = Player(lifecycle, playback, cancel_during_play)
        result = SpeechPresentationService(synthesizer, player, lifecycle).speak(response)
        return result, synthesizer, player

    def test_explicit_success_path_submits_once_and_presents_separately(self):
        observer = Observer()
        lifecycle = VoiceLifecycle(observer)
        controller, stt, transcription = self.listen(lifecycle)
        runtime = Runtime()
        governed = SpeechRuntimeAdapter(runtime).submit(transcription)

        self.assertEqual(controller.transition_history[0].value, "idle")
        self.assertEqual(stt.calls, 1)
        self.assertEqual(runtime.calls, ["  Ask GRACI exactly once?!  "])
        self.assertIs(governed, runtime.result)
        self.assertIs(lifecycle.state, SystemState.IDLE)

        response = AuthoritativeFinalResponse("GRACI completed the governed task.")
        presentation, synthesizer, player = self.present(lifecycle, response)
        self.assertIs(presentation.status, PresentationStatus.SPOKEN)
        self.assertIs(presentation.authoritative_response, response)
        self.assertEqual(response.text, "GRACI completed the governed task.")
        self.assertEqual(presentation.tts.authoritative_text, response.text)
        self.assertEqual(presentation.tts.presentation_text,
                         "GRAY-see completed the governed task.")
        self.assertIs(synthesizer.state_during_synthesis, SystemState.IDLE)
        self.assertIs(player.state_during_playback, SystemState.SPEAKING)
        self.assertEqual(runtime.calls, ["  Ask GRACI exactly once?!  "])
        self.assertEqual([event.state for event in observer.events], [
            SystemState.LISTENING, SystemState.IDLE,
            SystemState.SPEAKING, SystemState.IDLE])

    def test_rejected_failed_and_blank_transcriptions_submit_zero_times(self):
        cases = (
            TranscriptionResult(TranscriptionStatus.FAILED, "closure-fake-stt", 1.0,
                                error_code="rejected", error_message="rejected"),
            TranscriptionResult(TranscriptionStatus.SUCCESS, "closure-fake-stt", 1.0,
                                text=""),
            TranscriptionResult(TranscriptionStatus.SUCCESS, "closure-fake-stt", 1.0,
                                text=" \t\r\n "),
        )
        for value in cases:
            lifecycle, runtime = VoiceLifecycle(), Runtime()
            _, stt, transcription = self.listen(lifecycle, STT(value))
            with self.assertRaises(TranscriptSubmissionError):
                SpeechRuntimeAdapter(runtime).submit(transcription)
            self.assertEqual(stt.calls, 1)
            self.assertEqual(runtime.calls, [])
            self.assertIs(lifecycle.state, SystemState.IDLE)

    def test_runtime_success_is_independent_when_synthesis_fails(self):
        lifecycle, runtime = VoiceLifecycle(), Runtime()
        transcription = self.listen(lifecycle)[2]
        governed = SpeechRuntimeAdapter(runtime).submit(transcription)
        response = AuthoritativeFinalResponse("GRACI result remains authoritative.")
        presentation, synthesizer, player = self.present(
            lifecycle, response, tts_status=TTSStatus.FAILED)
        self.assertIs(governed, runtime.result)
        self.assertIs(presentation.status, PresentationStatus.FAILED)
        self.assertIs(presentation.authoritative_response, response)
        self.assertEqual(len(synthesizer.requests), 1)
        self.assertEqual(player.calls, [])
        self.assertEqual(runtime.calls, ["  Ask GRACI exactly once?!  "])
        self.assertIs(lifecycle.state, SystemState.IDLE)

    def test_runtime_success_is_independent_when_playback_fails(self):
        observer, runtime = Observer(), Runtime()
        lifecycle = VoiceLifecycle(observer)
        governed = SpeechRuntimeAdapter(runtime).submit(self.listen(lifecycle)[2])
        response = AuthoritativeFinalResponse("GRACI governed result.")
        failure = PlaybackResult(PlaybackStatus.FAILED, "device", "unavailable")
        presentation, synthesizer, player = self.present(lifecycle, response,
                                                         playback=failure)
        self.assertIs(governed, runtime.result)
        self.assertIs(presentation.status, PresentationStatus.FAILED)
        self.assertIs(presentation.playback, failure)
        self.assertIs(synthesizer.state_during_synthesis, SystemState.IDLE)
        self.assertIs(player.state_during_playback, SystemState.SPEAKING)
        self.assertEqual(runtime.calls, ["  Ask GRACI exactly once?!  "])
        self.assertIs(lifecycle.state, SystemState.IDLE)

    def test_publisher_failures_during_listening_and_speaking_are_isolated(self):
        observer = Observer((SystemState.LISTENING, SystemState.SPEAKING))
        lifecycle, runtime = VoiceLifecycle(observer), Runtime()
        transcription = self.listen(lifecycle)[2]
        governed = SpeechRuntimeAdapter(runtime).submit(transcription)
        response = AuthoritativeFinalResponse("GRACI still completes.")
        presentation = self.present(lifecycle, response)[0]
        self.assertIs(governed, runtime.result)
        self.assertTrue(transcription.succeeded)
        self.assertIs(presentation.status, PresentationStatus.SPOKEN)
        self.assertIs(presentation.authoritative_response, response)
        self.assertEqual(len(lifecycle.publication_failures), 2)
        self.assertEqual(len(runtime.calls), 1)
        self.assertIs(lifecycle.state, SystemState.IDLE)

    def test_listening_cancel_timeout_device_and_cleanup_failures_restore_idle(self):
        lifecycle = VoiceLifecycle()
        controller = PushToTalkController(Capture(), STT(), AudioCaptureConfig(), lifecycle)
        controller.begin()
        controller.cancel()
        self.assertIs(lifecycle.state, SystemState.IDLE)

        timeout = TranscriptionResult(TranscriptionStatus.FAILED, "closure-fake-stt", 1.0,
                                      error_code="stt_timeout", error_message="timeout")
        self.assertFalse(self.listen(lifecycle, STT(timeout))[2].succeeded)
        self.assertFalse(self.listen(lifecycle, session=Session(
            stop_error=OSError("device lost")))[2].succeeded)
        cleanup_controller = PushToTalkController(
            Capture(Session(cancel_error=OSError("cleanup failed"))), STT(),
            AudioCaptureConfig(), lifecycle)
        cleanup_controller.begin()
        with self.assertRaises(OSError):
            cleanup_controller.cancel()
        self.assertIs(lifecycle.state, SystemState.IDLE)

    def test_playback_cancel_and_stop_do_not_roll_back_governed_result(self):
        lifecycle, runtime = VoiceLifecycle(), Runtime()
        governed = SpeechRuntimeAdapter(runtime).submit(self.listen(lifecycle)[2])
        response = AuthoritativeFinalResponse("completed before optional speech")
        presentation, synthesizer, player = self.present(
            lifecycle, response, cancel_during_play=True)
        self.assertIs(presentation.status, PresentationStatus.CANCELLED)
        self.assertTrue(player.stopped)
        self.assertIs(governed, runtime.result)
        self.assertEqual(len(runtime.calls), 1)
        self.assertIs(lifecycle.state, SystemState.IDLE)
        service = SpeechPresentationService(synthesizer, player, lifecycle)
        service.stop()
        self.assertTrue(synthesizer.cancelled)
        self.assertIs(governed, runtime.result)
        self.assertEqual(len(runtime.calls), 1)

    def test_generation_guards_prevent_contradiction_and_late_restoration(self):
        observer = Observer()
        lifecycle = VoiceLifecycle(observer)
        old = lifecycle.enter(SystemState.LISTENING)
        contradictory = lifecycle.enter(SystemState.SPEAKING)
        self.assertFalse(contradictory.active)
        old.close()
        newer = lifecycle.enter(SystemState.SPEAKING)
        old.close()
        self.assertIs(lifecycle.state, SystemState.SPEAKING)
        newer.close()
        self.assertEqual([event.state for event in observer.events], [
            SystemState.LISTENING, SystemState.IDLE,
            SystemState.SPEAKING, SystemState.IDLE])

    def test_authoritative_boundary_is_explicit_and_synthesis_is_not_speaking(self):
        lifecycle = VoiceLifecycle()
        synthesizer, player = Synthesizer(lifecycle), Player(lifecycle)
        service = SpeechPresentationService(synthesizer, player, lifecycle)
        with self.assertRaises(TypeError):
            service.speak("GRACI raw text")
        self.assertEqual(synthesizer.requests, [])
        response = AuthoritativeFinalResponse("GRACI is written unchanged.")
        result = service.speak(response)
        self.assertIsInstance(synthesizer.requests[0], TTSRequest)
        self.assertIs(synthesizer.requests[0].authoritative_response, response)
        self.assertIs(synthesizer.state_during_synthesis, SystemState.IDLE)
        self.assertEqual(result.tts.authoritative_text, "GRACI is written unchanged.")
        self.assertEqual(result.tts.presentation_text, "GRAY-see is written unchanged.")

    def test_consolidated_closure_evidence_contract(self):
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads((root / "phase6" / "evidence" /
                               "phase6-closure.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["status"], "PASS")
        self.assertEqual(evidence["accepted_baseline_commit"],
                         "c5c7c2883e88751772818c8c49554d3a40270d8d")
        self.assertEqual(evidence["verification"]["integrated_tests_passed"], 10)
        self.assertEqual(evidence["verification"]["full_tests_passed"], 325)
        self.assertEqual(evidence["runtime_submission_counts"], {
            "accepted_transcript": 1, "failed_transcript": 0,
            "blank_transcript": 0, "presentation_side_effects": 0})
        self.assertFalse(evidence["architecture"]["autonomous_voice_loop"])
        verification = evidence["verification"]
        self.assertEqual(verification["compilation_scope"],
                         "GRACI-owned source and tests")
        cache_diagnostic = verification["excluded_third_party_cache_diagnostic"]
        self.assertFalse(cache_diagnostic["tracked"])
        self.assertFalse(cache_diagnostic["graci_source_failure"])
        requirements = evidence["deterministic_test_requirements"]
        self.assertTrue(all(value is False for value in requirements.values()))
        self.assertFalse(evidence["live_validation"]["physical_microphone_performed"])
        self.assertFalse(evidence["live_validation"]["physical_speaker_performed"])


if __name__ == "__main__":
    unittest.main()
