"""Deterministic Phase 6E voice lifecycle publication acceptance tests."""

import unittest

from graci.audio_capture import AudioCaptureConfig
from graci.push_to_talk import PushToTalkController
from graci.playback import PlaybackResult, PlaybackStatus
from graci.speech import CapturedAudio, TranscriptionResult, TranscriptionStatus
from graci.speech_presentation import PresentationStatus, SpeechPresentationService
from graci.tts import (AuthoritativeFinalResponse, SynthesizedAudio, TTSResult,
                       TTSStatus)
from graci.visualizer import SystemState
from graci.voice_lifecycle import VoiceLifecycle


class RecordingObserver:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    def publish(self, event):
        self.events.append(event)
        if self.fail:
            raise RuntimeError("observer offline")


class Session:
    def __init__(self, error=None):
        self.error = error
        self.cancelled = False

    def stop(self):
        if self.error:
            raise self.error
        return CapturedAudio(b"\0\0" * 16000, 16000, 1, 2)

    def cancel(self):
        self.cancelled = True
        if self.error:
            raise self.error


class Capture:
    def __init__(self, session=None, error=None):
        self.session = session or Session()
        self.error = error

    def start(self, config):
        if self.error:
            raise self.error
        return self.session


class STT:
    identity = "fake-local-stt"

    def __init__(self, result=None, error=None, inspect=None):
        self.result = result or TranscriptionResult(
            TranscriptionStatus.SUCCESS, self.identity, 1.0, text="hello")
        self.error = error
        self.inspect = inspect

    def transcribe(self, audio):
        if self.inspect:
            self.inspect()
        if self.error:
            raise self.error
        return self.result


def audio():
    return SynthesizedAudio(b"RIFFfake", 24000, 1, 2, 0.5)


class Synthesizer:
    def __init__(self, lifecycle, result=None):
        self.lifecycle = lifecycle
        self.observed = None
        self.result = result or TTSResult(TTSStatus.SUCCESS, "kokoro", "af_bella",
                                          "completed governed result",
                                          "completed governed result", audio())

    def synthesize(self, request):
        self.observed = self.lifecycle.state
        return self.result

    def cancel(self):
        pass


class Player:
    def __init__(self, lifecycle, result=None, error=None):
        self.lifecycle = lifecycle
        self.observed = None
        self.result = result or PlaybackResult(PlaybackStatus.SUCCESS)
        self.error = error

    def play(self, value):
        self.observed = self.lifecycle.state
        if self.error:
            raise self.error
        return self.result

    def stop(self):
        pass


class VoiceLifecycleTests(unittest.TestCase):
    def states(self, observer):
        return [event.state for event in observer.events]

    def controller(self, lifecycle, *, capture=None, stt=None):
        return PushToTalkController(capture or Capture(), stt or STT(),
                                    AudioCaptureConfig(), lifecycle)

    def test_listening_is_entered_only_during_bounded_activity_and_restored_on_success(self):
        observer = RecordingObserver()
        lifecycle = VoiceLifecycle(observer)
        controller = self.controller(
            lifecycle, stt=STT(inspect=lambda: self.assertIs(
                lifecycle.state, SystemState.IDLE)))
        self.assertIs(lifecycle.state, SystemState.IDLE)  # capability alone is idle
        controller.begin()
        self.assertIs(lifecycle.state, SystemState.LISTENING)
        self.assertTrue(controller.end_and_transcribe().succeeded)
        self.assertIs(lifecycle.state, SystemState.IDLE)
        self.assertEqual(self.states(observer), [SystemState.LISTENING, SystemState.IDLE])
        self.assertEqual([event.sequence for event in observer.events], [1, 2])

    def test_listening_restores_after_timeout_worker_and_device_failures(self):
        timeout = TranscriptionResult(TranscriptionStatus.FAILED, "fake-local-stt", 1.0,
                                      error_code="stt_timeout", error_message="timeout")
        cases = (
            (Capture(), STT(timeout)),
            (Capture(), STT(error=RuntimeError("worker crash"))),
            (Capture(Session(OSError("device lost"))), STT()),
        )
        for capture, stt in cases:
            with self.subTest(capture=capture, stt=stt):
                lifecycle = VoiceLifecycle()
                controller = self.controller(lifecycle, capture=capture, stt=stt)
                controller.begin()
                self.assertFalse(controller.end_and_transcribe().succeeded)
                self.assertIs(lifecycle.state, SystemState.IDLE)

    def test_listening_restores_after_cancel_start_failure_and_cancel_cleanup_exception(self):
        lifecycle = VoiceLifecycle()
        controller = self.controller(lifecycle)
        controller.begin()
        controller.cancel()
        self.assertIs(lifecycle.state, SystemState.IDLE)

        failed = self.controller(lifecycle, capture=Capture(error=OSError("no mic")))
        with self.assertRaises(OSError):
            failed.begin()
        self.assertIs(lifecycle.state, SystemState.IDLE)

        cleanup = self.controller(lifecycle, capture=Capture(Session(OSError("cleanup"))))
        cleanup.begin()
        with self.assertRaises(OSError):
            cleanup.cancel()
        self.assertIs(lifecycle.state, SystemState.IDLE)

    def presentation(self, lifecycle, playback=None, error=None):
        synth = Synthesizer(lifecycle)
        player = Player(lifecycle, playback, error)
        return SpeechPresentationService(synth, player, lifecycle), synth, player

    def test_speaking_wraps_playback_only_and_restores_on_success(self):
        observer = RecordingObserver()
        lifecycle = VoiceLifecycle(observer)
        service, synth, player = self.presentation(lifecycle)
        response = AuthoritativeFinalResponse("completed governed result")
        result = service.speak(response)
        self.assertIs(synth.observed, SystemState.IDLE)  # synthesis is not speaking
        self.assertIs(player.observed, SystemState.SPEAKING)
        self.assertIs(lifecycle.state, SystemState.IDLE)
        self.assertIs(result.authoritative_response, response)
        self.assertEqual(self.states(observer), [SystemState.SPEAKING, SystemState.IDLE])

    def test_speaking_restores_and_preserves_results_for_failure_timeout_cancel_and_exception(self):
        outcomes = (
            PlaybackResult(PlaybackStatus.FAILED, "device", "failed"),
            PlaybackResult(PlaybackStatus.TIMEOUT, "playback_timeout", "timeout"),
            PlaybackResult(PlaybackStatus.CANCELLED, "playback_cancelled", "cancelled"),
        )
        response = AuthoritativeFinalResponse("immutable completed result")
        for playback in outcomes:
            lifecycle = VoiceLifecycle()
            service, _, _ = self.presentation(lifecycle, playback)
            result = service.speak(response)
            self.assertIs(lifecycle.state, SystemState.IDLE)
            self.assertIs(result.authoritative_response, response)
            self.assertIs(result.playback, playback)
        lifecycle = VoiceLifecycle()
        result = self.presentation(lifecycle, error=OSError("device"))[0].speak(response)
        self.assertIs(result.status, PresentationStatus.FAILED)
        self.assertIs(result.authoritative_response, response)
        self.assertIs(lifecycle.state, SystemState.IDLE)

    def test_synthesis_failure_never_claims_speaking(self):
        observer = RecordingObserver()
        lifecycle = VoiceLifecycle(observer)
        synth = Synthesizer(lifecycle, TTSResult(TTSStatus.FAILED, "kokoro", "af_bella",
                                                "done", error_code="tts",
                                                error_message="bad"))
        result = SpeechPresentationService(synth, Player(lifecycle), lifecycle).speak(
            AuthoritativeFinalResponse("done"))
        self.assertIs(result.status, PresentationStatus.FAILED)
        self.assertEqual(observer.events, [])

    def test_contradictory_state_and_late_publication_are_prevented(self):
        observer = RecordingObserver()
        lifecycle = VoiceLifecycle(observer)
        listening = lifecycle.enter(SystemState.LISTENING)
        speaking = lifecycle.enter(SystemState.SPEAKING)
        self.assertFalse(speaking.active)
        self.assertIs(lifecycle.state, SystemState.LISTENING)
        speaking.close()
        listening.close()
        listening.close()
        self.assertEqual(self.states(observer), [SystemState.LISTENING, SystemState.IDLE])

    def test_publisher_failure_is_recorded_isolated_and_restoration_attempted(self):
        observer = RecordingObserver(fail=True)
        lifecycle = VoiceLifecycle(observer)
        controller = self.controller(lifecycle)
        controller.begin()
        result = controller.end_and_transcribe()
        self.assertTrue(result.succeeded)
        self.assertIs(lifecycle.state, SystemState.IDLE)
        self.assertEqual(len(lifecycle.publication_failures), 2)
        self.assertEqual(self.states(observer), [SystemState.LISTENING, SystemState.IDLE])

        response = AuthoritativeFinalResponse("authoritative")
        spoken = self.presentation(lifecycle)[0].speak(response)
        self.assertIs(spoken.authoritative_response, response)
        self.assertIs(spoken.status, PresentationStatus.SPOKEN)
        self.assertIs(lifecycle.state, SystemState.IDLE)


if __name__ == "__main__":
    unittest.main()
