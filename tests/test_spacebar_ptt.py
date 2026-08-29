"""Focused regression coverage for Windows-local Spacebar hold-to-talk input."""

import unittest

from graci.keyboard_input import HoldSpacebarToTalk, KeyEvent, VK_SPACE
from graci.speech import TranscriptionResult, TranscriptionStatus
from graci.turn_coordinator import ExplicitTurnCoordinator


class Runtime:
    def __init__(self):
        self.calls = []

    def run(self, task):
        self.calls.append(task)
        return {"status": "PASS"}


class PushToTalk:
    def __init__(self, transcription=None, *, begin_error=None, finish_error=None):
        self.transcription = transcription or TranscriptionResult(
            TranscriptionStatus.SUCCESS, "fake", 0.5, text="one spoken task")
        self.begin_error = begin_error
        self.finish_error = finish_error
        self.begins = 0
        self.finishes = 0
        self.cancels = 0

    def begin(self):
        self.begins += 1
        if self.begin_error:
            raise self.begin_error

    def end_and_transcribe(self):
        self.finishes += 1
        if self.finish_error:
            raise self.finish_error
        return self.transcription

    def cancel(self):
        self.cancels += 1


class Keyboard:
    def __init__(self, *events):
        self.events = iter(events)

    def next_event(self):
        return next(self.events)


class SpacebarPushToTalkTests(unittest.TestCase):
    @staticmethod
    def setup(transcription=None, **ptt_options):
        runtime = Runtime()
        ptt = PushToTalk(transcription, **ptt_options)
        return runtime, ptt, ExplicitTurnCoordinator(runtime, push_to_talk=ptt)

    def test_first_down_begins_once_repeat_is_ignored_and_up_finishes_once(self):
        runtime, ptt, coordinator = self.setup()
        driver = HoldSpacebarToTalk(Keyboard(
            KeyEvent(VK_SPACE, True),
            KeyEvent(VK_SPACE, True),
            KeyEvent(VK_SPACE, False),
        ))
        result = driver.run(coordinator)
        self.assertEqual((ptt.begins, ptt.finishes, ptt.cancels), (1, 1, 0))
        self.assertEqual(runtime.calls, ["one spoken task"])
        self.assertTrue(result.governed_submitted)

    def test_unrelated_keys_and_release_without_press_do_nothing(self):
        runtime, ptt, coordinator = self.setup()
        driver = HoldSpacebarToTalk(Keyboard())
        self.assertIsNone(driver.handle_event(KeyEvent(0x41, True), coordinator))
        self.assertIsNone(driver.handle_event(KeyEvent(0x41, False), coordinator))
        self.assertIsNone(driver.handle_event(KeyEvent(VK_SPACE, False), coordinator))
        self.assertEqual((ptt.begins, ptt.finishes, runtime.calls), (0, 0, []))

    def test_capture_or_stt_failure_never_submits(self):
        failed = TranscriptionResult(TranscriptionStatus.FAILED, "fake", 0.2,
                                     error_code="stt_failed", error_message="failed")
        cases = ({"begin_error": OSError("no microphone")},
                 {"finish_error": OSError("capture failed")},
                 {"transcription": failed})
        for options in cases:
            with self.subTest(options=options):
                transcription = options.pop("transcription", None)
                runtime, ptt, coordinator = self.setup(transcription, **options)
                result = HoldSpacebarToTalk(Keyboard(
                    KeyEvent(VK_SPACE, True), KeyEvent(VK_SPACE, False))).run(coordinator)
                self.assertFalse(result.governed_submitted)
                self.assertEqual(runtime.calls, [])

    def test_input_failure_during_hold_cancels_without_submission(self):
        runtime, ptt, coordinator = self.setup()
        driver = HoldSpacebarToTalk(Keyboard(KeyEvent(VK_SPACE, True)))
        with self.assertRaises(StopIteration):
            driver.run(coordinator)
        self.assertEqual((ptt.begins, ptt.finishes, ptt.cancels), (1, 0, 1))
        self.assertEqual(runtime.calls, [])


if __name__ == "__main__":
    unittest.main()
