"""Authority, cancellation, and bounded rolling-STT regression tests."""

import threading
import time
import unittest

from graci.browser_ptt import BrowserPTTOperator
from graci.speech import CapturedAudio, TranscriptionResult, TranscriptionStatus
from graci.streaming_stt import DeferredStreamingTranscriber
from graci.visualizer import SystemState
from graci.voice_lifecycle import VoiceLifecycle
from tests.test_browser_ptt import Coordinator, STT, wav_bytes


def audio(seconds: float) -> CapturedAudio:
    return CapturedAudio(b"\0\0" * int(16_000 * seconds), 16_000, 1, 2)


class BlockingSTT:
    identity = "local-test"

    def __init__(self):
        self.calls = []
        self.started = threading.Event()
        self.release = threading.Event()

    def transcribe(self, captured):
        self.calls.append(captured)
        self.started.set()
        self.release.wait(2)
        return TranscriptionResult(TranscriptionStatus.SUCCESS, self.identity,
                                   captured.duration_seconds,
                                   text="alpha beta beta gamma")


class SessionSTT(BlockingSTT):
    def __init__(self):
        super().__init__()
        self.closed = 0

    def close(self):
        self.closed += 1
        self.release.set()


class SessionFactory:
    identity = "local-session-test"

    def __init__(self):
        self.opens = 0
        self.session = SessionSTT()

    def open_stream(self):
        self.opens += 1
        return self.session

    def transcribe(self, _captured):
        raise AssertionError("turn-scoped streaming session was not reused")


class DeferredStreamingTests(unittest.TestCase):
    def test_incremental_work_starts_before_release_and_final_is_single_text(self):
        stt = BlockingSTT()
        streaming = DeferredStreamingTranscriber(stt)
        offered = audio(1.0)
        self.assertTrue(streaming.offer(offered))
        self.assertTrue(stt.started.wait(1))
        self.assertEqual(len(stt.calls), 1)
        stt.release.set()
        result = streaming.finalize(offered)
        self.assertEqual(result.text, "alpha beta beta gamma")
        self.assertEqual(len(stt.calls), 1)  # identical final audio reuses the safe snapshot

    def test_latest_only_snapshots_and_cancel_discard_without_output(self):
        stt = BlockingSTT()
        streaming = DeferredStreamingTranscriber(stt)
        streaming.offer(audio(.6))
        self.assertTrue(stt.started.wait(1))
        streaming.offer(audio(.8))
        streaming.offer(audio(1.0))
        stt.release.set()
        streaming.cancel()
        self.assertLessEqual(len(stt.calls), 2)

    def test_one_session_per_turn_bounds_preview_and_closes_after_final(self):
        factory = SessionFactory()
        factory.session.release.set()
        streaming = DeferredStreamingTranscriber(factory)
        streaming.offer(audio(1.0))
        self.assertTrue(factory.session.started.wait(1))
        result = streaming.finalize(audio(5.0))
        self.assertTrue(result.succeeded)
        self.assertEqual(factory.opens, 1)
        self.assertEqual(factory.session.closed, 1)
        self.assertEqual([round(call.duration_seconds, 1)
                          for call in factory.session.calls], [1.0, 5.0])

    def test_preview_window_is_bounded_to_three_seconds(self):
        stt = BlockingSTT()
        stt.release.set()
        streaming = DeferredStreamingTranscriber(stt)
        streaming.offer(audio(8.0))
        self.assertTrue(stt.started.wait(1))
        streaming.cancel()
        self.assertEqual(stt.calls[0].duration_seconds, 3.0)

    def test_obsolete_preview_cannot_hold_release_to_worker_timeout(self):
        factory = SessionFactory()
        streaming = DeferredStreamingTranscriber(factory)
        streaming.offer(audio(1.0))
        self.assertTrue(factory.session.started.wait(1))
        started = time.monotonic()
        result = streaming.finalize(audio(4.0))
        self.assertLess(time.monotonic() - started, 2)
        self.assertTrue(result.succeeded)
        self.assertEqual(factory.opens, 2)

    def test_browser_partial_never_reaches_coordinator_and_cancel_runs_zero(self):
        coordinator = Coordinator()
        lifecycle = VoiceLifecycle()
        operator = BrowserPTTOperator(STT(), coordinator, lifecycle)
        token = operator.begin()
        self.assertTrue(operator.offer(token, wav_bytes(.6)))
        self.assertEqual(coordinator.calls, [])
        self.assertEqual(lifecycle.state, SystemState.LISTENING)
        operator.cancel(token)
        self.assertEqual(coordinator.calls, [])
        self.assertEqual(lifecycle.state, SystemState.IDLE)

    def test_browser_offer_then_release_submits_exactly_once(self):
        stt, coordinator = STT(), Coordinator()
        operator = BrowserPTTOperator(stt, coordinator, VoiceLifecycle())
        token = operator.begin()
        operator.offer(token, wav_bytes(.6))
        result = operator.finish(token, wav_bytes(.8))
        self.assertIsNotNone(result.turn_result)
        self.assertEqual(coordinator.calls, ["hello GRACI"])


if __name__ == "__main__":
    unittest.main()
