"""Narrow loopback browser push-to-talk adapter for the resident GRACI host."""

from __future__ import annotations

import io
import logging
import secrets
import threading
import wave
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .audio_capture import AudioCaptureConfig
from .speech import CapturedAudio, SpeechToText, TranscriptionResult
from .streaming_stt import DeferredStreamingTranscriber
from .turn_coordinator import ExplicitTurnCoordinator, TurnResult
from .visualizer import SystemState
from .voice_lifecycle import VoiceLifecycle, VoiceLifecycleLease


MAX_BROWSER_AUDIO_BYTES = 4_000_000
TOKEN_BYTES = 24
_LOG = logging.getLogger(__name__)


class BrowserPTTStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True)
class BrowserPTTResult:
    status: BrowserPTTStatus
    turn_result: TurnResult | None = None
    transcription: TranscriptionResult | None = None
    error_code: str | None = None
    error_message: str | None = None


class BrowserPTTBusy(RuntimeError):
    pass


class BrowserPTTInvalid(RuntimeError):
    pass


class BrowserPTTOperator:
    """Own one explicit browser hold and feed its transcript to the existing coordinator."""

    def __init__(self, stt: SpeechToText, coordinator: ExplicitTurnCoordinator,
                 lifecycle: VoiceLifecycle, config: AudioCaptureConfig = AudioCaptureConfig(),
                 interrupt_speaking: Callable[[], None] | None = None,
                 completed_turn_observer: Callable[[TurnResult], None] | None = None):
        self._stt = stt
        self._coordinator = coordinator
        self._lifecycle = lifecycle
        self._config = config
        self._interrupt_speaking = interrupt_speaking
        self._completed_turn_observer = completed_turn_observer
        self._lock = threading.Lock()
        self._token: str | None = None
        self._processing = 0
        self._lease: VoiceLifecycleLease | None = None
        self._timer: threading.Timer | None = None
        self._streaming: DeferredStreamingTranscriber | None = None

    @property
    def active(self) -> bool:
        with self._lock:
            return self._token is not None or self._processing

    def begin(self) -> str:
        with self._lock:
            if self._token is not None:
                raise BrowserPTTBusy("a browser operator turn is already active")
            if self._processing and self._lifecycle.state is not SystemState.SPEAKING:
                raise BrowserPTTBusy("a browser operator turn is already active")
            lease = self._lifecycle.enter_listening(self._interrupt_speaking)
            if not lease.active:
                raise BrowserPTTBusy("another explicit operator activity owns the coordinator")
            token = secrets.token_urlsafe(TOKEN_BYTES)
            timer = threading.Timer(self._config.max_duration_seconds, self._expire,
                                    args=(token,))
            timer.daemon = True
            self._token, self._lease, self._timer = token, lease, timer
            self._streaming = DeferredStreamingTranscriber(self._stt)
            timer.start()
            return token

    def finish(self, token: str, wav_bytes: bytes) -> BrowserPTTResult:
        lease = self._take(token, processing=True)
        streaming, self._streaming = self._streaming, None
        lease.close()  # LISTENING ends before validation/STT, matching local PTT semantics.
        try:
            return self._finish_audio(wav_bytes, streaming)
        finally:
            if streaming is not None:
                streaming.cancel()
            with self._lock:
                self._processing -= 1

    def _finish_audio(self, wav_bytes: bytes,
                      streaming: DeferredStreamingTranscriber | None) -> BrowserPTTResult:
        try:
            audio = decode_browser_wav(wav_bytes, self._config)
        except BrowserPTTInvalid as exc:
            return BrowserPTTResult(BrowserPTTStatus.REJECTED, error_code="invalid_audio",
                                    error_message=str(exc)[:500])
        if audio.duration_seconds < self._config.minimum_duration_seconds:
            return BrowserPTTResult(BrowserPTTStatus.REJECTED,
                                    error_code="insufficient_audio",
                                    error_message="recording contained no meaningful audio")
        try:
            transcription = (streaming.finalize(audio) if streaming is not None
                             else self._stt.transcribe(audio))
        except Exception as exc:
            return BrowserPTTResult(BrowserPTTStatus.FAILED, error_code="stt_failed",
                                    error_message=str(exc)[:500])
        if not transcription.succeeded:
            return BrowserPTTResult(BrowserPTTStatus.REJECTED, transcription=transcription,
                                    error_code=transcription.error_code or "transcription_failed",
                                    error_message=transcription.error_message or "speech transcription failed")
        if not isinstance(transcription.text, str) or not transcription.text.strip():
            return BrowserPTTResult(BrowserPTTStatus.REJECTED, transcription=transcription,
                                    error_code="blank_transcript",
                                    error_message="speech transcription produced no text")
        # Browser PTT is a voice modality: the existing coordinator constructs one
        # authoritative response and presents that same object through Phase 6D.
        result = self._coordinator.run_typed(transcription.text, present_speech=True)
        if (self._completed_turn_observer is not None
                and getattr(result, "governed_submitted", False)
                and getattr(result, "governed_result", None) is not None):
            try:
                self._completed_turn_observer(result)
            except Exception as exc:
                _LOG.warning("latest-turn observer failed (%s): %s",
                             type(exc).__name__, exc)
        return BrowserPTTResult(BrowserPTTStatus.ACCEPTED, result, transcription)

    def offer(self, token: str, wav_bytes: bytes) -> bool:
        """Accept one transient rolling snapshot without submission or publication."""
        with self._lock:
            if token != self._token or self._streaming is None:
                raise BrowserPTTInvalid("invalid or expired browser PTT turn")
            streaming = self._streaming
        return streaming.offer(decode_browser_wav(wav_bytes, self._config))

    def cancel(self, token: str) -> None:
        lease = self._take(token, processing=False)
        streaming, self._streaming = self._streaming, None
        if streaming is not None:
            streaming.cancel()
        lease.close()

    def close(self) -> None:
        with self._lock:
            token = self._token
        if token is not None:
            try:
                self.cancel(token)
            except BrowserPTTInvalid:
                pass

    def _take(self, token: str, *, processing: bool) -> VoiceLifecycleLease:
        if not isinstance(token, str) or not 20 <= len(token) <= 128:
            raise BrowserPTTInvalid("invalid or expired browser PTT turn")
        with self._lock:
            if token != self._token or self._lease is None:
                raise BrowserPTTInvalid("invalid or expired browser PTT turn")
            lease, timer = self._lease, self._timer
            self._token = self._lease = self._timer = None
            if processing:
                self._processing += 1
            if timer is not None:
                timer.cancel()
            return lease

    def _expire(self, token: str) -> None:
        try:
            self.cancel(token)
        except BrowserPTTInvalid:
            pass


def decode_browser_wav(data: bytes, config: AudioCaptureConfig) -> CapturedAudio:
    if not isinstance(data, bytes) or not data or len(data) > MAX_BROWSER_AUDIO_BYTES:
        raise BrowserPTTInvalid("audio body is blank or exceeds the upload limit")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            frames = wav.getnframes()
            compression = wav.getcomptype()
            pcm = wav.readframes(frames)
            if wav.readframes(1):
                raise BrowserPTTInvalid("audio contains trailing frames")
    except (EOFError, wave.Error) as exc:
        raise BrowserPTTInvalid("audio must be a valid PCM WAV") from exc
    if (channels, width, compression) != (config.channels, config.sample_width, "NONE"):
        raise BrowserPTTInvalid("audio must be mono 16-bit PCM WAV")
    if rate < 8_000 or rate > 48_000:
        raise BrowserPTTInvalid("audio sample rate is outside the supported range")
    if frames <= 0 or len(pcm) != frames * channels * width:
        raise BrowserPTTInvalid("audio contains no complete PCM frames")
    audio = CapturedAudio(pcm, rate, channels, width)
    if audio.duration_seconds > config.max_duration_seconds:
        raise BrowserPTTInvalid("audio duration exceeds the push-to-talk limit")
    return audio
