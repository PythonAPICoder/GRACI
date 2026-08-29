"""Explicit, single-turn composition over accepted GRACI interaction boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from .speech import TranscriptionResult
from .speech_presentation import SpeechPresentationResult, SpeechPresentationService
from .speech_runtime import GovernedRuntime
from .tts import AuthoritativeFinalResponse


class InputSource(str, Enum):
    TYPED = "typed"
    SPEECH = "speech"


class InputOutcome(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


class TurnDisposition(str, Enum):
    INPUT_REJECTED = "input_rejected"
    INPUT_FAILED = "input_failed"
    GOVERNED_PASS = "governed_pass"
    GOVERNED_FAIL = "governed_fail"
    GOVERNED_ERROR = "governed_error"


class PushToTalk(Protocol):
    def begin(self) -> None: ...
    def end_and_transcribe(self) -> TranscriptionResult: ...


class FinalResponseConstructor(Protocol):
    """Explicit authority for selecting final user-facing text from a governed result."""

    def construct(self, governed_result: dict[str, Any]) -> AuthoritativeFinalResponse | None: ...


@dataclass(frozen=True)
class TurnResult:
    input_source: InputSource
    input_outcome: InputOutcome
    transcription: TranscriptionResult | None
    governed_submitted: bool
    governed_result: dict[str, Any] | None
    authoritative_response: AuthoritativeFinalResponse | None
    speech_requested: bool
    speech_presentation: SpeechPresentationResult | None
    disposition: TurnDisposition
    error_code: str | None = None
    error_message: str | None = None


class ExplicitTurnCoordinator:
    """Coordinate at most one governed submission for one caller-initiated turn."""

    def __init__(self, runtime: GovernedRuntime, *, push_to_talk: PushToTalk | None = None,
                 final_response_constructor: FinalResponseConstructor | None = None,
                 speech_presentation: SpeechPresentationService | None = None):
        self._runtime = runtime
        self._push_to_talk = push_to_talk
        self._final_response_constructor = final_response_constructor
        self._speech_presentation = speech_presentation
        self._speech_active = False

    def run_typed(self, text: str, *, present_speech: bool = False) -> TurnResult:
        if not isinstance(text, str) or not text.strip():
            return self._rejected(InputSource.TYPED, present_speech, "blank_input",
                                  "typed input must be a non-empty string")
        return self._submit(InputSource.TYPED, text, None, present_speech)

    def begin_speech_turn(self) -> TurnResult | None:
        """Begin one explicit push-to-talk turn; return a terminal result on start failure."""
        if self._push_to_talk is None:
            return self._failed(InputSource.SPEECH, False, "speech_unavailable",
                                "push-to-talk input is not configured")
        if self._speech_active:
            return self._failed(InputSource.SPEECH, False, "speech_turn_active",
                                "a speech turn is already active")
        try:
            self._push_to_talk.begin()
        except Exception as exc:
            return self._failed(InputSource.SPEECH, False, "speech_start_failed", str(exc))
        self._speech_active = True
        return None

    def finish_speech_turn(self, *, present_speech: bool = False) -> TurnResult:
        if self._push_to_talk is None or not self._speech_active:
            return self._failed(InputSource.SPEECH, present_speech, "no_active_speech_turn",
                                "no explicitly initiated speech turn is active")
        self._speech_active = False
        try:
            transcription = self._push_to_talk.end_and_transcribe()
        except Exception as exc:
            return self._failed(InputSource.SPEECH, present_speech,
                                "speech_acquisition_failed", str(exc))
        if not isinstance(transcription, TranscriptionResult):
            return self._failed(InputSource.SPEECH, present_speech,
                                "invalid_transcription_result",
                                "push-to-talk returned an invalid transcription result")
        if not transcription.succeeded:
            return self._rejected(
                InputSource.SPEECH, present_speech,
                transcription.error_code or "transcription_failed",
                transcription.error_message or "speech transcription failed",
                transcription=transcription,
            )
        if not isinstance(transcription.text, str) or not transcription.text.strip():
            return self._rejected(InputSource.SPEECH, present_speech, "blank_transcript",
                                  "successful transcription contained no text",
                                  transcription=transcription)
        return self._submit(InputSource.SPEECH, transcription.text, transcription,
                            present_speech)

    def _submit(self, source: InputSource, task: str,
                transcription: TranscriptionResult | None,
        present_speech: bool) -> TurnResult:
        # This is the coordinator's sole governed submission statement.
        try:
            governed = self._runtime.run(task)
        except Exception as exc:
            return TurnResult(source, InputOutcome.ACCEPTED, transcription, True, None,
                              None, present_speech, None,
                              TurnDisposition.GOVERNED_ERROR,
                              "governed_runtime_exception", str(exc)[:500])
        response = None
        presentation = None
        error_code = error_message = None
        if self._final_response_constructor is not None:
            try:
                response = self._final_response_constructor.construct(governed)
                if response is not None and not isinstance(response, AuthoritativeFinalResponse):
                    raise TypeError("constructor must return AuthoritativeFinalResponse or None")
            except Exception as exc:
                response = None
                error_code = "final_response_construction_failed"
                error_message = str(exc)[:500]
        if present_speech:
            if response is None:
                if error_code is None:
                    error_code = "authoritative_response_unavailable"
                    error_message = "speech requires an explicitly constructed authoritative response"
            elif self._speech_presentation is None:
                error_code = "speech_presentation_unavailable"
                error_message = "speech presentation was requested but is not configured"
            else:
                presentation = self._speech_presentation.speak(response)
        disposition = (TurnDisposition.GOVERNED_PASS
                       if governed.get("status") == "PASS"
                       else TurnDisposition.GOVERNED_FAIL)
        return TurnResult(source, InputOutcome.ACCEPTED, transcription, True, governed,
                          response, present_speech, presentation, disposition,
                          error_code, error_message)

    @staticmethod
    def _rejected(source: InputSource, speech: bool, code: str, message: str,
                  *, transcription: TranscriptionResult | None = None) -> TurnResult:
        return TurnResult(source, InputOutcome.REJECTED, transcription, False, None,
                          None, speech, None, TurnDisposition.INPUT_REJECTED,
                          code, message[:500])

    @staticmethod
    def _failed(source: InputSource, speech: bool, code: str, message: str) -> TurnResult:
        return TurnResult(source, InputOutcome.FAILED, None, False, None, None,
                          speech, None, TurnDisposition.INPUT_FAILED, code, message[:500])
