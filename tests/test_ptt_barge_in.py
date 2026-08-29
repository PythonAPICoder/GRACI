"""Focused explicit PTT interruption tests; governed and STT authority stay unchanged."""

import threading
import time
import unittest
from queue import Empty, Queue

from graci.browser_ptt import BrowserPTTOperator
from graci.push_to_talk import PushToTalkController
from graci.keyboard_input import HoldSpacebarToTalk, KeyEvent, VK_SPACE
from graci.playback import PlaybackResult, PlaybackStatus
from graci.speech import TranscriptionResult, TranscriptionStatus
from graci.speech_presentation import PresentationStatus, SpeechPresentationService
from graci.tts import AuthoritativeFinalResponse, SynthesizedAudio, TTSResult, TTSStatus
from graci.turn_coordinator import ExplicitTurnCoordinator
from graci.visualizer import SystemState
from graci.voice_lifecycle import VoiceLifecycle
from tests.test_browser_ptt import wav_bytes


class Runtime:
    def __init__(self):
        self.calls = []

    def run(self, task):
        self.calls.append(task)
        return {"status": "PASS", "validated_model_result": {"user_response": f"answer:{task}"}}


class Constructor:
    def __init__(self):
        self.responses = []

    def construct(self, governed):
        response = AuthoritativeFinalResponse(governed["validated_model_result"]["user_response"])
        self.responses.append(response)
        return response


class TTS:
    def synthesize(self, request):
        audio = SynthesizedAudio(b"RIFFbarge-in", 24_000, 1, 2, 1.0)
        return TTSResult(TTSStatus.SUCCESS, "Kokoro-82M-ONNX:cpu", "af_heart",
                         request.authoritative_response.text, "GRAY-see", audio)

    def cancel(self):
        pass


class FirstPlaybackBlocks:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.stops = 0
        self.calls = 0

    def play(self, _audio):
        self.calls += 1
        if self.calls == 1:
            self.started.set()
            self.release.wait(2)
            return PlaybackResult(PlaybackStatus.CANCELLED, "playback_cancelled", "cancelled")
        return PlaybackResult(PlaybackStatus.SUCCESS)

    def stop(self):
        self.stops += 1
        self.release.set()


class STT:
    identity = "local"

    def __init__(self, texts):
        self._texts = iter(texts)

    def transcribe(self, audio):
        return TranscriptionResult(TranscriptionStatus.SUCCESS, self.identity,
                                   audio.duration_seconds, next(self._texts))


class LifecyclePTT:
    def __init__(self, lifecycle, interrupt, texts):
        self.lifecycle = lifecycle
        self.interrupt = interrupt
        self.texts = iter(texts)
        self.lease = None
        self.begins = self.finishes = self.cancels = 0

    def begin(self):
        self.begins += 1
        self.lease = self.lifecycle.enter_listening(self.interrupt)
        if not self.lease.active:
            raise RuntimeError("voice busy")

    def end_and_transcribe(self):
        self.finishes += 1
        self.lease.close()
        return TranscriptionResult(TranscriptionStatus.SUCCESS, "local", .2, next(self.texts))

    def cancel(self):
        self.cancels += 1
        self.lease.close()


class ExplicitPTTBargeInTests(unittest.TestCase):
    def composition(self, *, browser=False):
        lifecycle = VoiceLifecycle()
        runtime, constructor, player = Runtime(), Constructor(), FirstPlaybackBlocks()
        presentation = SpeechPresentationService(TTS(), player, lifecycle)
        ptt = None if browser else LifecyclePTT(lifecycle, presentation.interrupt_playback,
                                                ["new cli turn", "barge cli turn"])
        coordinator = ExplicitTurnCoordinator(
            runtime, push_to_talk=ptt, final_response_constructor=constructor,
            speech_presentation=presentation)
        operator = (BrowserPTTOperator(STT(["first browser turn", "new browser turn"]),
                                       coordinator, lifecycle,
                                       interrupt_speaking=presentation.interrupt_playback)
                    if browser else None)
        return lifecycle, runtime, constructor, player, coordinator, operator

    def test_browser_press_stops_playback_enters_listening_and_release_submits_once(self):
        lifecycle, runtime, constructor, player, _, operator = self.composition(browser=True)
        first_token = operator.begin()
        first = []
        thread = threading.Thread(target=lambda: first.append(operator.finish(first_token, wav_bytes())))
        thread.start()
        self.assertTrue(player.started.wait(1))
        self.assertIs(lifecycle.state, SystemState.SPEAKING)

        started = time.monotonic()
        second_token = operator.begin()
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, .5)
        self.assertEqual(player.stops, 1)
        self.assertIs(lifecycle.state, SystemState.LISTENING)
        self.assertEqual(runtime.calls, ["first browser turn"])
        self.assertEqual(constructor.responses[0].text, "answer:first browser turn")

        second = operator.finish(second_token, wav_bytes())
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(runtime.calls, ["first browser turn", "new browser turn"])
        self.assertEqual(first[0].turn_result.speech_presentation.status,
                         PresentationStatus.CANCELLED)
        self.assertEqual(constructor.responses[0].text, "answer:first browser turn")
        self.assertTrue(second.turn_result.governed_submitted)

    def test_browser_cancel_after_barge_in_submits_nothing_new(self):
        lifecycle, runtime, _, player, _, operator = self.composition(browser=True)
        token = operator.begin()
        thread = threading.Thread(target=lambda: operator.finish(token, wav_bytes()))
        thread.start(); self.assertTrue(player.started.wait(1))
        barge_token = operator.begin()
        operator.cancel(barge_token)
        thread.join(1)
        self.assertEqual(runtime.calls, ["first browser turn"])
        self.assertIs(lifecycle.state, SystemState.IDLE)

    def test_cli_spacebar_press_barges_without_submission_and_release_submits_once(self):
        lifecycle, runtime, constructor, player, coordinator, _ = self.composition()
        first = []
        thread = threading.Thread(
            target=lambda: first.append(coordinator.run_typed("first cli turn", present_speech=True)))
        thread.start(); self.assertTrue(player.started.wait(1))
        driver = HoldSpacebarToTalk(type("Keyboard", (), {})())

        self.assertIsNone(driver.handle_event(KeyEvent(VK_SPACE, True), coordinator,
                                              present_speech=True))
        self.assertIs(lifecycle.state, SystemState.LISTENING)
        self.assertEqual(runtime.calls, ["first cli turn"])
        result = driver.handle_event(KeyEvent(VK_SPACE, False), coordinator,
                                     present_speech=True)
        thread.join(1)
        self.assertEqual(runtime.calls, ["first cli turn", "new cli turn"])
        self.assertTrue(result.governed_submitted)
        self.assertEqual(constructor.responses[0].text, "answer:first cli turn")

    def test_cli_run_keeps_polling_spacebar_while_playback_blocks(self):
        lifecycle, runtime, _, player, coordinator, _ = self.composition()

        class TimedKeyboard:
            def __init__(self):
                self.events = Queue()
                self.events.put(KeyEvent(VK_SPACE, True))
                self.events.put(KeyEvent(VK_SPACE, False))

            def next_event(self, timeout_seconds=None):
                try:
                    return self.events.get(timeout=timeout_seconds)
                except Empty:
                    return None

        keyboard = TimedKeyboard()
        result = []
        thread = threading.Thread(
            target=lambda: result.append(
                HoldSpacebarToTalk(keyboard).run(coordinator, present_speech=True)))
        thread.start()
        self.assertTrue(player.started.wait(1))
        self.assertIs(lifecycle.state, SystemState.SPEAKING)
        keyboard.events.put(KeyEvent(VK_SPACE, True))
        self.assertTrue(self._wait_for(lambda: lifecycle.state is SystemState.LISTENING))
        self.assertEqual(runtime.calls, ["new cli turn"])
        keyboard.events.put(KeyEvent(VK_SPACE, False))
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(runtime.calls, ["new cli turn", "barge cli turn"])
        self.assertTrue(result[0].governed_submitted)
        self.assertEqual(player.stops, 1)

    @staticmethod
    def _wait_for(predicate, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(.005)
        return predicate()

    def test_repeated_cli_press_and_cancel_create_no_governed_turn(self):
        lifecycle, runtime, _, player, coordinator, _ = self.composition()
        thread = threading.Thread(
            target=lambda: coordinator.run_typed("first cli turn", present_speech=True))
        thread.start(); self.assertTrue(player.started.wait(1))
        driver = HoldSpacebarToTalk(type("Keyboard", (), {})())
        self.assertIsNone(driver.handle_event(KeyEvent(VK_SPACE, True), coordinator))
        self.assertIsNone(driver.handle_event(KeyEvent(VK_SPACE, True), coordinator))
        coordinator.cancel_speech_turn()
        driver._capture_active = False
        thread.join(1)
        self.assertEqual(runtime.calls, ["first cli turn"])
        self.assertIs(lifecycle.state, SystemState.IDLE)

    def test_natural_finish_race_and_late_stop_are_bounded(self):
        lifecycle = VoiceLifecycle()
        speaking = lifecycle.enter(SystemState.SPEAKING)
        calls = []

        def natural_finish_during_stop():
            calls.append("stop")
            speaking.close()

        listening = lifecycle.enter_listening(natural_finish_during_stop)
        self.assertTrue(listening.active)
        self.assertIs(lifecycle.state, SystemState.LISTENING)
        listening.close()
        late = lifecycle.enter_listening(lambda: calls.append("late"))
        self.assertTrue(late.active)
        self.assertEqual(calls, ["stop"])
        late.close()

    def test_interruption_or_capture_start_failure_fails_without_submission(self):
        lifecycle = VoiceLifecycle()
        speaking = lifecycle.enter(SystemState.SPEAKING)
        with self.assertRaisesRegex(RuntimeError, "stop failed"):
            lifecycle.enter_listening(lambda: (_ for _ in ()).throw(RuntimeError("stop failed")))
        self.assertIs(lifecycle.state, SystemState.SPEAKING)
        speaking.close()

        class Capture:
            def start(self, _config):
                raise OSError("microphone unavailable")

        lifecycle.enter(SystemState.SPEAKING)
        controller = PushToTalkController(Capture(), STT([]), lifecycle=lifecycle,
                                          interrupt_speaking=lambda: None)
        with self.assertRaisesRegex(OSError, "microphone unavailable"):
            controller.begin()
        self.assertIs(lifecycle.state, SystemState.IDLE)


if __name__ == "__main__":
    unittest.main()
