"""Bounded local text-to-speech contracts and Kokoro subprocess adapter."""

from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import wave
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from phase6a.pronunciation import MAX_TTS_TEXT_CHARS, speech_presentation_text

MAX_SYNTHESIZED_AUDIO_BYTES = 8 * 1024 * 1024
MAX_SYNTHESIZED_AUDIO_SECONDS = 120.0


class TTSStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class AuthoritativeFinalResponse:
    """Text explicitly selected by the caller as the final user-facing response."""

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("authoritative final response text must be a string")
        if not self.text.strip():
            raise ValueError("authoritative final response text must not be blank")
        if len(self.text) > MAX_TTS_TEXT_CHARS:
            raise ValueError("authoritative final response exceeds the TTS input bound")


@dataclass(frozen=True)
class TTSRequest:
    authoritative_response: AuthoritativeFinalResponse

    def __post_init__(self) -> None:
        if not isinstance(self.authoritative_response, AuthoritativeFinalResponse):
            raise TypeError("TTS requires an explicit AuthoritativeFinalResponse")


@dataclass(frozen=True)
class SynthesizedAudio:
    wav_bytes: bytes
    sample_rate: int
    channels: int
    sample_width: int
    duration_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.wav_bytes, bytes) or not self.wav_bytes:
            raise ValueError("synthesized WAV must contain bytes")
        if len(self.wav_bytes) > MAX_SYNTHESIZED_AUDIO_BYTES:
            raise ValueError("synthesized WAV exceeds the audio byte bound")
        if not 8_000 <= self.sample_rate <= 48_000:
            raise ValueError("synthesized sample rate is out of bounds")
        if self.channels != 1 or self.sample_width != 2:
            raise ValueError("Phase 6D playback requires mono 16-bit PCM")
        if not 0 < self.duration_seconds <= MAX_SYNTHESIZED_AUDIO_SECONDS:
            raise ValueError("synthesized audio duration is out of bounds")


@dataclass(frozen=True)
class TTSResult:
    status: TTSStatus
    engine: str
    voice: str
    authoritative_text: str
    presentation_text: str | None = None
    audio: SynthesizedAudio | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is TTSStatus.SUCCESS


@dataclass(frozen=True)
class KokoroConfig:
    python_executable: Path
    worker_script: Path
    model_path: Path
    voices_path: Path
    voice: str = "af_bella"
    device: str = "cpu"
    timeout_seconds: float = 60.0
    max_audio_bytes: int = MAX_SYNTHESIZED_AUDIO_BYTES
    max_audio_seconds: float = MAX_SYNTHESIZED_AUDIO_SECONDS

    def __post_init__(self) -> None:
        if self.voice != "af_bella":
            raise ValueError("Phase 6D production voice is fixed to af_bella")
        if self.device != "cpu":
            raise ValueError("Phase 6D Kokoro synthesis is fixed to local CPU")
        if not 0 < self.timeout_seconds <= 120:
            raise ValueError("synthesis timeout must be in (0, 120]")
        if not 1 <= self.max_audio_bytes <= MAX_SYNTHESIZED_AUDIO_BYTES:
            raise ValueError("invalid synthesized audio byte bound")
        if not 0 < self.max_audio_seconds <= MAX_SYNTHESIZED_AUDIO_SECONDS:
            raise ValueError("invalid synthesized audio duration bound")


class KokoroSubprocessTTS:
    """Runs the qualified local Kokoro environment once per explicit request."""

    identity = "Kokoro-82M-ONNX:cpu"

    def __init__(self, config: KokoroConfig):
        self.config = config
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._cancel_requested = False
        self._last_cleanup_error: str | None = None

    def synthesize(self, request: TTSRequest) -> TTSResult:
        self._last_cleanup_error = None
        result = self._synthesize(request)
        if self._last_cleanup_error is not None:
            return self._failure(result.authoritative_text,
                                 result.presentation_text or result.authoritative_text,
                                 "tts_cleanup_failed", self._last_cleanup_error)
        return result

    def _synthesize(self, request: TTSRequest) -> TTSResult:
        if not isinstance(request, TTSRequest):
            raise TypeError("request must be a TTSRequest")
        authoritative = request.authoritative_response.text
        presentation = speech_presentation_text(authoritative)
        if not self._lock.acquire(blocking=False):
            return self._failure(authoritative, presentation, "synthesis_busy",
                                 "one synthesis operation is already outstanding")
        text_path: Path | None = None
        audio_path: Path | None = None
        try:
            self._cancel_requested = False
            with tempfile.NamedTemporaryFile(prefix="graci-tts-text-", suffix=".txt",
                                             delete=False) as text_file:
                text_path = Path(text_file.name)
                text_file.write(presentation.encode("utf-8"))
            with tempfile.NamedTemporaryFile(prefix="graci-tts-audio-", suffix=".wav",
                                             delete=False) as audio_file:
                audio_path = Path(audio_file.name)
            command = [str(self.config.python_executable), str(self.config.worker_script),
                       "--text-file", str(text_path), "--output", str(audio_path),
                       "--model", str(self.config.model_path),
                       "--voices", str(self.config.voices_path),
                       "--voice", self.config.voice, "--device", self.config.device,
                       "--max-text-chars", str(MAX_TTS_TEXT_CHARS),
                       "--max-audio-bytes", str(self.config.max_audio_bytes),
                       "--max-audio-seconds", str(self.config.max_audio_seconds)]
            self._process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, text=True)
            try:
                stdout, stderr = self._process.communicate(timeout=self.config.timeout_seconds)
            except subprocess.TimeoutExpired:
                self._terminate()
                return TTSResult(TTSStatus.TIMEOUT, self.identity, self.config.voice,
                                 authoritative, presentation, error_code="synthesis_timeout",
                                 error_message="local Kokoro synthesis timed out")
            if self._cancel_requested:
                return TTSResult(TTSStatus.CANCELLED, self.identity, self.config.voice,
                                 authoritative, presentation, error_code="synthesis_cancelled",
                                 error_message="synthesis was cancelled")
            if self._process.returncode != 0:
                return self._failure(authoritative, presentation, "tts_worker_failed",
                                     (stderr.strip() or "local Kokoro worker failed")[:500])
            try:
                payload = json.loads(stdout)
                if set(payload) != {"status", "voice", "device"}:
                    raise ValueError("worker response fields are invalid")
                if payload != {"status": "success", "voice": "af_bella", "device": "cpu"}:
                    raise ValueError("worker response identity is invalid")
                audio = self._read_audio(audio_path)
            except (EOFError, json.JSONDecodeError, OSError, ValueError, wave.Error) as exc:
                return self._failure(authoritative, presentation, "invalid_tts_response", str(exc))
            return TTSResult(TTSStatus.SUCCESS, self.identity, self.config.voice,
                             authoritative, presentation, audio=audio)
        except OSError as exc:
            return self._failure(authoritative, presentation, "tts_unavailable", str(exc))
        finally:
            self._process = None
            for path in (text_path, audio_path):
                if path is not None:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError as exc:
                        self._last_cleanup_error = str(exc)[:500]
            self._lock.release()

    def cancel(self) -> None:
        self._cancel_requested = True
        self._terminate()

    def _terminate(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    def _read_audio(self, path: Path) -> SynthesizedAudio:
        size = path.stat().st_size
        if size > self.config.max_audio_bytes:
            raise ValueError("synthesized WAV exceeds configured byte bound")
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            frames = wav.getnframes()
            duration = frames / rate if rate else 0.0
        if duration > self.config.max_audio_seconds:
            raise ValueError("synthesized WAV exceeds configured duration bound")
        return SynthesizedAudio(path.read_bytes(), rate, channels, width, duration)

    def _failure(self, authoritative: str, presentation: str, code: str,
                 message: str) -> TTSResult:
        return TTSResult(TTSStatus.FAILED, self.identity, self.config.voice,
                         authoritative, presentation, error_code=code,
                         error_message=message[:500])
