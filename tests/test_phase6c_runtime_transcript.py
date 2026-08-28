import unittest

from graci.speech import TranscriptionResult, TranscriptionStatus
from graci.speech_runtime import SpeechRuntimeAdapter, TranscriptSubmissionError


class FakeGovernedRuntime:
    def __init__(self, result=None, error=None):
        self.result = result or {"status": "PASS", "validated_model_result": {"summary": "done"}}
        self.error = error
        self.tasks = []

    def run(self, task):
        self.tasks.append(task)
        if self.error:
            raise self.error
        return self.result


def success(text):
    return TranscriptionResult(TranscriptionStatus.SUCCESS, "fake-local-stt", .25, text=text)


class SpeechRuntimeAdapterTests(unittest.TestCase):
    def test_success_submits_once_and_returns_existing_runtime_result(self):
        runtime = FakeGovernedRuntime()
        result = SpeechRuntimeAdapter(runtime).submit(success("hello GRACI"))
        self.assertIs(result, runtime.result)
        self.assertEqual(runtime.tasks, ["hello GRACI"])

    def test_exact_transcript_text_is_preserved(self):
        runtime = FakeGovernedRuntime()
        text = "  Keep THIS punctuation, please?!  "
        SpeechRuntimeAdapter(runtime).submit(success(text))
        self.assertEqual(runtime.tasks, [text])

    def test_failed_transcription_is_rejected_without_runtime_call(self):
        runtime = FakeGovernedRuntime()
        failed = TranscriptionResult(TranscriptionStatus.FAILED, "fake-local-stt", .25,
                                     error_code="model_error", error_message="unavailable")
        with self.assertRaisesRegex(TranscriptSubmissionError, "model_error"):
            SpeechRuntimeAdapter(runtime).submit(failed)
        self.assertEqual(runtime.tasks, [])

    def test_empty_and_whitespace_transcripts_are_rejected(self):
        for text in (None, "", " \t\r\n "):
            with self.subTest(text=text):
                runtime = FakeGovernedRuntime()
                with self.assertRaises(TranscriptSubmissionError):
                    SpeechRuntimeAdapter(runtime).submit(success(text))
                self.assertEqual(runtime.tasks, [])

    def test_invalid_runtime_submission_and_runtime_failure_remain_explicit(self):
        error = RuntimeError("governed runtime unavailable")
        runtime = FakeGovernedRuntime(error=error)
        with self.assertRaisesRegex(RuntimeError, "governed runtime unavailable"):
            SpeechRuntimeAdapter(runtime).submit(success("run this"))
        self.assertEqual(runtime.tasks, ["run this"])

        failed_result = {"status": "FAIL", "errors": ["validation_error: invalid response"]}
        runtime = FakeGovernedRuntime(result=failed_result)
        self.assertIs(SpeechRuntimeAdapter(runtime).submit(success("run this")), failed_result)

    def test_sequential_transcripts_use_the_same_runtime_boundary(self):
        runtime = FakeGovernedRuntime()
        adapter = SpeechRuntimeAdapter(runtime)
        adapter.submit(success("first"))
        adapter.submit(success("second"))
        self.assertEqual(runtime.tasks, ["first", "second"])

    def test_speech_and_typed_input_follow_identical_governed_path(self):
        runtime = FakeGovernedRuntime()
        typed_result = runtime.run("equivalent input")
        speech_result = SpeechRuntimeAdapter(runtime).submit(success("equivalent input"))
        self.assertIs(typed_result, runtime.result)
        self.assertIs(speech_result, runtime.result)
        self.assertEqual(runtime.tasks, ["equivalent input", "equivalent input"])

    def test_no_tts_or_secondary_execution_is_triggered(self):
        runtime = FakeGovernedRuntime()
        SpeechRuntimeAdapter(runtime).submit(success("one governed turn"))
        self.assertEqual(len(runtime.tasks), 1)


if __name__ == "__main__":
    unittest.main()
