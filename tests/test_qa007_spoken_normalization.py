"""QA-007 spoken response normalization and authority-boundary tests."""

import contextlib
import io
import json
import struct
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from graci.__main__ import main
from graci.browser_ptt import BrowserPTTOperator
from graci.operator_cli import GovernedSummaryResponseConstructor
from graci.playback import PlaybackResult, PlaybackStatus
from graci.provider import LocalLlamaCppProvider
from graci.speech import TranscriptionResult, TranscriptionStatus
from graci.speech_presentation import SpeechPresentationService
from graci.speech_normalization import normalize_spoken_text
from graci.tts import (AuthoritativeFinalResponse, KokoroConfig, KokoroSubprocessTTS,
                       SynthesizedAudio, TTSRequest, TTSResult, TTSStatus)
from graci.turn_coordinator import ExplicitTurnCoordinator
from graci.voice_lifecycle import VoiceLifecycle
from phase6a.pronunciation import speech_presentation_text


class SpokenNormalizationTests(unittest.TestCase):
    def test_common_markdown_is_natural_speech(self):
        cases = {
            "**This is important**": "This is important",
            "- item one": "item one",
            "# Heading": "Heading",
            "Use `plain words` here.": "Use plain words here.",
            "See [useful documentation](https://example.test/path).":
                "See useful documentation.",
            "***": "",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(normalize_spoken_text(source), expected)

    def test_multiple_emphasis_spans_do_not_leave_symbol_names(self):
        rendered = speech_presentation_text(
            "**GRACI** says *this* is **important** and __clear__.")
        self.assertEqual(rendered, "GRAY-see says this is important and clear.")
        self.assertNotIn("*", rendered)

    def test_authoritative_copy_is_byte_for_byte_unchanged_and_order_is_explicit(self):
        source = "# **GRACI** uses `*.py`"
        response = AuthoritativeFinalResponse(source)
        self.assertEqual(speech_presentation_text(response.text),
                         "GRAY-see uses *.py")
        self.assertEqual(response.text.encode("utf-8"), source.encode("utf-8"))

    def test_literal_character_question_and_technical_content_are_preserved(self):
        self.assertEqual(normalize_spoken_text("What does * mean?"), "What does * mean?")
        technical = "Run `git add *.py`, use `value**2`, or evaluate $x * y$."
        self.assertEqual(normalize_spoken_text(technical),
                         "Run git add *.py, use value**2, or evaluate $x * y$.")

    def test_normalization_failure_stops_before_kokoro_without_mutating_authority(self):
        response = AuthoritativeFinalResponse("**GRACI** remains authoritative")
        config = KokoroConfig(Path("python.exe"), Path("worker.py"), Path("model"), Path("voices"))
        with patch("graci.tts.speech_presentation_text", side_effect=RuntimeError("normalize")), \
             patch("graci.tts.subprocess.Popen") as popen:
            with self.assertRaisesRegex(RuntimeError, "normalize"):
                KokoroSubprocessTTS(config).synthesize(TTSRequest(response))
        popen.assert_not_called()
        self.assertEqual(response.text, "**GRACI** remains authoritative")


class _Runtime:
    def __init__(self):
        self.calls = []

    def run(self, task):
        self.calls.append(task)
        return {"status": "PASS", "validated_model_result": {
            "schema_version": 2, "status": "PASS", "summary": "complete",
            "user_response": "**GRACI** says:\n- **item one**",
        }}


class _NormalizingTTS:
    def __init__(self):
        self.presentation_text = None

    def synthesize(self, request):
        source = request.authoritative_response.text
        self.presentation_text = speech_presentation_text(source)
        audio = SynthesizedAudio(b"RIFFqa007", 24_000, 1, 2, .1)
        return TTSResult(TTSStatus.SUCCESS, "test", "af_heart", source,
                         self.presentation_text, audio)

    def cancel(self):
        pass


class _Player:
    def play(self, audio):
        return PlaybackResult(PlaybackStatus.SUCCESS)

    def stop(self):
        pass


class ProductionEntryPathTests(unittest.TestCase):
    def coordinator(self):
        runtime = _Runtime()
        tts = _NormalizingTTS()
        coordinator = ExplicitTurnCoordinator(
            runtime, final_response_constructor=GovernedSummaryResponseConstructor(),
            speech_presentation=SpeechPresentationService(tts, _Player()))
        return coordinator, tts, runtime

    def test_cli_speak_uses_normalized_speech_path(self):
        coordinator, tts, _ = self.coordinator()
        output = io.StringIO()
        with patch("graci.__main__.resident_is_active", return_value=False), \
             contextlib.redirect_stdout(output):
            code = main(["task", "--speak"], coordinator_factory=lambda: coordinator)
        self.assertEqual(code, 0)
        self.assertEqual(tts.presentation_text, "GRAY-see says:\nitem one")
        self.assertEqual(json.loads(output.getvalue())["final_response"]["text"],
                         "**GRACI** says:\n- **item one**")

    def test_browser_ptt_uses_normalized_speech_path(self):
        coordinator, tts, _ = self.coordinator()

        class STT:
            def transcribe(self, audio):
                return TranscriptionResult(TranscriptionStatus.SUCCESS, "test", .2, "task")

        wav_output = io.BytesIO()
        with wave.open(wav_output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16_000)
            wav.writeframes(struct.pack("<h", 100) * 3_200)
        operator = BrowserPTTOperator(STT(), coordinator, VoiceLifecycle())
        result = operator.finish(operator.begin(), wav_output.getvalue())
        self.assertEqual(tts.presentation_text, "GRAY-see says:\nitem one")
        self.assertEqual(result.turn_result.authoritative_response.text,
                         "**GRACI** says:\n- **item one**")

    def test_normalization_failure_cannot_alter_or_rerun_governed_result(self):
        coordinator, _, runtime = self.coordinator()
        with patch("graci.tts.speech_presentation_text", side_effect=RuntimeError("normalize")):
            # Exercise the real adapter boundary rather than the recording test double.
            coordinator._speech_presentation._synthesizer = KokoroSubprocessTTS(
                KokoroConfig(Path("python.exe"), Path("worker.py"),
                             Path("model"), Path("voices")))
            result = coordinator.run_typed("task", present_speech=True)
        self.assertEqual(runtime.calls, ["task"])
        self.assertEqual(result.governed_result["status"], "PASS")
        self.assertEqual(result.authoritative_response.text,
                         "**GRACI** says:\n- **item one**")
        self.assertEqual(result.speech_presentation.error_code, "synthesis_exception")


class GovernanceFailurePresentationTests(unittest.TestCase):
    def test_runtime_governance_request_contract_requires_bounded_explanation(self):
        captured = {}
        config = type("Config", (), {
            "model": "local-model", "endpoint": "http://localhost", "timeout_seconds": 1,
        })()

        def transport(request, timeout):
            captured["body"] = request.data.decode("utf-8")
            return 200, (b'{"choices":[{"message":{"content":"{}"}}],'
                         b'"model":"local-model"}')

        LocalLlamaCppProvider(config, transport=transport).execute(
            "Add the special-character rule to governance")
        prompt = captured["body"]
        self.assertIn("cannot mutate its runtime governance", prompt)
        self.assertIn("do not claim to perform it", prompt)
        self.assertIn("clear, bounded explanation", prompt)

    def test_fail_closed_result_still_cannot_become_authoritative_response(self):
        governed = {"status": "FAIL", "validated_model_result": {
            "schema_version": 2, "status": "FAIL", "summary": "mutation unavailable",
            "user_response": None,
        }}
        self.assertIsNone(GovernedSummaryResponseConstructor().construct(governed))


if __name__ == "__main__":
    unittest.main()
