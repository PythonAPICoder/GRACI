"""Deterministic Phase 6B push-to-talk lifecycle orchestration."""

from __future__ import annotations

import threading
from enum import Enum

from .audio_capture import AudioCapture, AudioCaptureConfig, CaptureSession
from .speech import SpeechToText, TranscriptionResult, TranscriptionStatus


class PushToTalkState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"


class PushToTalkLifecycleError(RuntimeError):
    pass


class PushToTalkController:
    def __init__(self, capture: AudioCapture, stt: SpeechToText,
                 config: AudioCaptureConfig = AudioCaptureConfig()):
        self._capture = capture
        self._stt = stt
        self._config = config
        self._state = PushToTalkState.IDLE
        self._session: CaptureSession | None = None
        self._lock = threading.RLock()
        self._transition_history: list[PushToTalkState] = [self._state]

    @property
    def state(self) -> PushToTalkState:
        with self._lock:
            return self._state

    @property
    def transition_history(self) -> tuple[PushToTalkState, ...]:
        with self._lock:
            return tuple(self._transition_history)

    def begin(self) -> None:
        with self._lock:
            self._require(PushToTalkState.IDLE)
            try:
                self._session = self._capture.start(self._config)
            except Exception:
                self._set_state(PushToTalkState.FAILED)
                self._set_state(PushToTalkState.IDLE)
                raise
            self._set_state(PushToTalkState.RECORDING)

    def end_and_transcribe(self) -> TranscriptionResult:
        with self._lock:
            self._require(PushToTalkState.RECORDING)
            session = self._session
            self._session = None
            assert session is not None
        try:
            audio = session.stop()
        except Exception as exc:
            with self._lock:
                result = self._failure("capture_failed", str(exc), 0.0)
                self._finish(PushToTalkState.FAILED)
            return result
        with self._lock:
            if audio.duration_seconds < self._config.minimum_duration_seconds:
                result = self._failure("insufficient_audio", "recording contained no meaningful audio",
                                       audio.duration_seconds)
                self._finish(PushToTalkState.FAILED)
                return result
            self._set_state(PushToTalkState.TRANSCRIBING)
        try:
            result = self._stt.transcribe(audio)
        except Exception as exc:
            result = self._failure("stt_failed", str(exc), audio.duration_seconds)
        with self._lock:
            self._finish(PushToTalkState.COMPLETED if result.succeeded else PushToTalkState.FAILED)
        return result

    def cancel(self) -> None:
        with self._lock:
            self._require(PushToTalkState.RECORDING)
            session = self._session
            self._session = None
            assert session is not None
            try:
                session.cancel()
            finally:
                self._set_state(PushToTalkState.IDLE)

    def _failure(self, code: str, message: str, duration: float) -> TranscriptionResult:
        return TranscriptionResult(TranscriptionStatus.FAILED, self._stt.identity, duration,
                                   error_code=code, error_message=message[:500])

    def _finish(self, terminal: PushToTalkState) -> None:
        self._set_state(terminal)
        self._set_state(PushToTalkState.IDLE)

    def _set_state(self, state: PushToTalkState) -> None:
        self._state = state
        self._transition_history.append(state)

    def _require(self, expected: PushToTalkState) -> None:
        if self._state is not expected:
            raise PushToTalkLifecycleError(f"operation requires {expected.value}; current state is {self._state.value}")
