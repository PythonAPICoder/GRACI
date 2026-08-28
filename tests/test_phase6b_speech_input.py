import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from graci.audio_capture import AudioCaptureConfig, AudioCaptureError
from graci.push_to_talk import (PushToTalkController, PushToTalkLifecycleError,
                                PushToTalkState)
from graci.speech import (CapturedAudio, FasterWhisperConfig,
                          FasterWhisperSubprocessSTT, TranscriptionResult,
                          TranscriptionStatus)


def audio(seconds=0.25):
    return CapturedAudio(b"\0\0" * int(16_000 * seconds), 16_000, 1, 2)


class FakeSession:
    def __init__(self, captured=None, stop_error=None):
        self.captured = captured or audio()
        self.stop_error = stop_error
        self.cancelled = False
        self.stopped = False

    def stop(self):
        self.stopped = True
        if self.stop_error:
            raise self.stop_error
        return self.captured

    def cancel(self):
        self.cancelled = True


class FakeCapture:
    def __init__(self, sessions=None, error=None):
        self.sessions = list(sessions or [FakeSession()])
        self.error = error
        self.starts = 0

    def start(self, config):
        self.starts += 1
        if self.error:
            raise self.error
        return self.sessions.pop(0)


class FakeSTT:
    identity = "fake-local-stt"

    def __init__(self, results=None, error=None):
        self.results = list(results or [])
        self.error = error
        self.calls = []

    def transcribe(self, captured):
        self.calls.append(captured)
        if self.error:
            raise self.error
        if self.results:
            return self.results.pop(0)
        return TranscriptionResult(TranscriptionStatus.SUCCESS, self.identity,
                                   captured.duration_seconds, text="hello GRACI")


class PushToTalkTests(unittest.TestCase):
    def test_successful_lifecycle_and_result(self):
        capture, stt = FakeCapture(), FakeSTT()
        controller = PushToTalkController(capture, stt)
        controller.begin()
        self.assertEqual(controller.state, PushToTalkState.RECORDING)
        result = controller.end_and_transcribe()
        self.assertTrue(result.succeeded)
        self.assertEqual(result.text, "hello GRACI")
        self.assertEqual(result.backend, "fake-local-stt")
        self.assertEqual(controller.state, PushToTalkState.IDLE)
        self.assertEqual(controller.transition_history,
                         (PushToTalkState.IDLE, PushToTalkState.RECORDING,
                          PushToTalkState.TRANSCRIBING, PushToTalkState.COMPLETED,
                          PushToTalkState.IDLE))

    def test_repeated_cycles(self):
        controller = PushToTalkController(FakeCapture([FakeSession(), FakeSession()]), FakeSTT())
        for _ in range(2):
            controller.begin()
            self.assertTrue(controller.end_and_transcribe().succeeded)
        self.assertEqual(controller.state, PushToTalkState.IDLE)

    def test_capture_startup_failure_returns_to_idle_and_raises(self):
        controller = PushToTalkController(FakeCapture(error=AudioCaptureError("no device")), FakeSTT())
        with self.assertRaisesRegex(AudioCaptureError, "no device"):
            controller.begin()
        self.assertEqual(controller.state, PushToTalkState.IDLE)
        self.assertEqual(controller.transition_history[-2:],
                         (PushToTalkState.FAILED, PushToTalkState.IDLE))

    def test_capture_failure_is_explicit_and_skips_stt(self):
        stt = FakeSTT()
        controller = PushToTalkController(FakeCapture([FakeSession(stop_error=AudioCaptureError("lost"))]), stt)
        controller.begin()
        result = controller.end_and_transcribe()
        self.assertEqual(result.error_code, "capture_failed")
        self.assertIsNone(result.text)
        self.assertFalse(stt.calls)
        self.assertEqual(controller.state, PushToTalkState.IDLE)

    def test_stt_failure_is_explicit(self):
        failed = TranscriptionResult(TranscriptionStatus.FAILED, "fake-local-stt", .25,
                                     error_code="model_error", error_message="bad model")
        controller = PushToTalkController(FakeCapture(), FakeSTT([failed]))
        controller.begin()
        result = controller.end_and_transcribe()
        self.assertFalse(result.succeeded)
        self.assertIsNone(result.text)
        self.assertEqual(controller.transition_history[-2], PushToTalkState.FAILED)

    def test_unexpected_stt_exception_is_contained(self):
        controller = PushToTalkController(FakeCapture(), FakeSTT(error=RuntimeError("boom")))
        controller.begin()
        result = controller.end_and_transcribe()
        self.assertEqual(result.error_code, "stt_failed")
        self.assertEqual(controller.state, PushToTalkState.IDLE)

    def test_empty_or_insufficient_audio_skips_stt(self):
        stt = FakeSTT()
        controller = PushToTalkController(FakeCapture([FakeSession(audio(.05))]), stt)
        controller.begin()
        result = controller.end_and_transcribe()
        self.assertEqual(result.error_code, "insufficient_audio")
        self.assertFalse(stt.calls)

    def test_cancel_discards_session_and_returns_idle(self):
        session = FakeSession()
        controller = PushToTalkController(FakeCapture([session]), FakeSTT())
        controller.begin()
        controller.cancel()
        self.assertTrue(session.cancelled)
        self.assertEqual(controller.state, PushToTalkState.IDLE)

    def test_invalid_lifecycle_operations_are_rejected(self):
        controller = PushToTalkController(FakeCapture(), FakeSTT())
        with self.assertRaises(PushToTalkLifecycleError):
            controller.end_and_transcribe()
        with self.assertRaises(PushToTalkLifecycleError):
            controller.cancel()
        controller.begin()
        with self.assertRaises(PushToTalkLifecycleError):
            controller.begin()

    def test_transcribing_state_is_observable_and_rejects_overlap(self):
        entered, release = threading.Event(), threading.Event()
        class BlockingSTT(FakeSTT):
            def transcribe(self, captured):
                entered.set()
                release.wait(2)
                return super().transcribe(captured)
        controller = PushToTalkController(FakeCapture(), BlockingSTT())
        controller.begin()
        thread = threading.Thread(target=controller.end_and_transcribe)
        thread.start()
        self.assertTrue(entered.wait(1))
        self.assertEqual(controller.state, PushToTalkState.TRANSCRIBING)
        with self.assertRaises(PushToTalkLifecycleError):
            controller.begin()
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(controller.state, PushToTalkState.IDLE)

    def test_configuration_bounds(self):
        with self.assertRaises(ValueError):
            AudioCaptureConfig(channels=2)
        with self.assertRaises(ValueError):
            AudioCaptureConfig(max_duration_seconds=121)


class FasterWhisperAdapterTests(unittest.TestCase):
    def config(self, retained=False, directory=None):
        return FasterWhisperConfig(Path("python.exe"), Path("worker.py"),
                                   model_cache=Path("cache"), retain_audio=retained,
                                   retained_audio_directory=directory)

    def test_success_uses_local_worker_contract_and_cleans_temporary_wav(self):
        seen = {}
        def run(command, **kwargs):
            path = Path(command[command.index("--audio") + 1])
            seen["path"] = path
            seen["exists_during_run"] = path.exists()
            seen["command"] = command
            return subprocess.CompletedProcess(command, 0, '{"text":"local words"}', "")
        with patch("graci.speech.subprocess.run", side_effect=run):
            result = FasterWhisperSubprocessSTT(self.config()).transcribe(audio())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.text, "local words")
        self.assertTrue(seen["exists_during_run"])
        self.assertFalse(seen["path"].exists())
        self.assertIn("--device", seen["command"])
        self.assertIn("cpu", seen["command"])

    def test_worker_failure_and_timeout_have_no_manufactured_text(self):
        failed = subprocess.CompletedProcess([], 2, "", "model unavailable")
        with patch("graci.speech.subprocess.run", return_value=failed):
            result = FasterWhisperSubprocessSTT(self.config()).transcribe(audio())
        self.assertEqual(result.error_code, "stt_worker_failed")
        self.assertIsNone(result.text)
        with patch("graci.speech.subprocess.run", side_effect=subprocess.TimeoutExpired([], 1)):
            result = FasterWhisperSubprocessSTT(self.config()).transcribe(audio())
        self.assertEqual(result.error_code, "stt_timeout")

    def test_invalid_or_empty_worker_response_fails_explicitly(self):
        with patch("graci.speech.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 0, "not json", "")):
            result = FasterWhisperSubprocessSTT(self.config()).transcribe(audio())
        self.assertEqual(result.error_code, "invalid_stt_response")
        with patch("graci.speech.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 0, '{"text":""}', "")):
            result = FasterWhisperSubprocessSTT(self.config()).transcribe(audio())
        self.assertEqual(result.error_code, "empty_transcript")

    def test_explicit_debug_retention_keeps_wav(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("graci.speech.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 0, '{"text":"kept"}', "")):
                FasterWhisperSubprocessSTT(self.config(True, Path(directory))).transcribe(audio())
            retained = list(Path(directory).glob("graci-*.wav"))
            self.assertEqual(len(retained), 1)

    def test_runtime_configuration_rejects_non_cpu_mode(self):
        with self.assertRaises(ValueError):
            FasterWhisperConfig(Path("python"), Path("worker"), device="cuda")


if __name__ == "__main__":
    unittest.main()
