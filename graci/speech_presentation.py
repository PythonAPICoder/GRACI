"""Failure-isolated presentation of an authoritative final response."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .playback import PlaybackResult, PlaybackStatus
from .tts import AuthoritativeFinalResponse, TTSRequest, TTSResult, TTSStatus
from .visualizer import SystemState
from .voice_lifecycle import VoiceLifecycle


class Synthesizer(Protocol):
    def synthesize(self, request: TTSRequest) -> TTSResult: ...
    def cancel(self) -> None: ...


class Player(Protocol):
    def play(self, audio: object) -> PlaybackResult: ...
    def stop(self) -> None: ...


class PresentationStatus(str, Enum):
    SPOKEN = "spoken"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class SpeechPresentationResult:
    status: PresentationStatus
    authoritative_response: AuthoritativeFinalResponse
    tts: TTSResult | None = None
    playback: PlaybackResult | None = None
    error_code: str | None = None
    error_message: str | None = None


class SpeechPresentationService:
    """Presentation-only coordinator; it has no governed runtime dependency."""

    def __init__(self, synthesizer: Synthesizer, player: Player,
                 lifecycle: VoiceLifecycle | None = None):
        self._synthesizer = synthesizer
        self._player = player
        self._lifecycle = lifecycle

    def speak(self, response: AuthoritativeFinalResponse) -> SpeechPresentationResult:
        if not isinstance(response, AuthoritativeFinalResponse):
            raise TypeError("speak requires an explicit AuthoritativeFinalResponse")
        try:
            tts = self._synthesizer.synthesize(TTSRequest(response))
        except Exception as exc:
            return SpeechPresentationResult(PresentationStatus.FAILED, response,
                                            error_code="synthesis_exception",
                                            error_message=str(exc)[:500])
        if not tts.succeeded or tts.audio is None:
            status = (PresentationStatus.CANCELLED if tts.status is TTSStatus.CANCELLED
                      else PresentationStatus.FAILED)
            return SpeechPresentationResult(status, response, tts=tts,
                                            error_code=tts.error_code,
                                            error_message=tts.error_message)
        try:
            lease = (self._lifecycle.enter(SystemState.SPEAKING)
                     if self._lifecycle is not None else None)
            try:
                playback = self._player.play(tts.audio)
            finally:
                if lease is not None:
                    lease.close()
        except Exception as exc:
            return SpeechPresentationResult(PresentationStatus.FAILED, response, tts=tts,
                                            error_code="playback_exception",
                                            error_message=str(exc)[:500])
        status = PresentationStatus.SPOKEN if playback.succeeded else (
            PresentationStatus.CANCELLED if playback.status is PlaybackStatus.CANCELLED
            else PresentationStatus.FAILED)
        return SpeechPresentationResult(status, response, tts=tts, playback=playback,
                                        error_code=playback.error_code,
                                        error_message=playback.error_message)

    def stop(self) -> None:
        self._synthesizer.cancel()
        self._player.stop()

    cancel = stop

    def interrupt_playback(self) -> None:
        """Stop only the owned playback copy; authoritative response remains untouched."""
        self._player.stop()
