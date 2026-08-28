"""Governed runtime submission boundary for successful speech transcripts."""

from __future__ import annotations

from typing import Any, Protocol

from .speech import TranscriptionResult


class GovernedRuntime(Protocol):
    """The same user-input boundary used by typed runtime callers."""

    def run(self, task: str) -> dict[str, Any]: ...


class TranscriptSubmissionError(ValueError):
    """A transcription cannot be submitted as governed user input."""


class SpeechRuntimeAdapter:
    """Validate speech transport output and submit its text without rewriting it."""

    def __init__(self, runtime: GovernedRuntime):
        self._runtime = runtime

    def submit(self, transcription: TranscriptionResult) -> dict[str, Any]:
        if not isinstance(transcription, TranscriptionResult):
            raise TranscriptSubmissionError("transcription must be a TranscriptionResult")
        if not transcription.succeeded:
            detail = transcription.error_code or "unknown_stt_failure"
            raise TranscriptSubmissionError(f"cannot submit failed transcription: {detail}")
        if not isinstance(transcription.text, str) or not transcription.text.strip():
            raise TranscriptSubmissionError("successful transcription must contain non-empty text")
        return self._runtime.run(transcription.text)
