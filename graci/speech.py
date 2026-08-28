"""Typed, local-only speech input primitives for Phase 6B."""

from __future__ import annotations

import json
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


class TranscriptionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class CapturedAudio:
    pcm: bytes
    sample_rate: int
    channels: int
    sample_width: int

    @property
    def duration_seconds(self) -> float:
        denominator = self.sample_rate * self.channels * self.sample_width
        return len(self.pcm) / denominator if denominator else 0.0


@dataclass(frozen=True)
class TranscriptionResult:
    status: TranscriptionStatus
    backend: str
    duration_seconds: float
    text: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is TranscriptionStatus.SUCCESS


class SpeechToText(Protocol):
    @property
    def identity(self) -> str: ...

    def transcribe(self, audio: CapturedAudio) -> TranscriptionResult: ...


@dataclass(frozen=True)
class FasterWhisperConfig:
    python_executable: Path
    worker_script: Path
    model: str = "small.en"
    model_cache: Path = Path("phase6a/cache")
    device: str = "cpu"
    compute_type: str = "int8"
    timeout_seconds: float = 120.0
    retain_audio: bool = False
    retained_audio_directory: Path | None = None

    def __post_init__(self) -> None:
        if self.device != "cpu" or self.compute_type != "int8":
            raise ValueError("Phase 6B production STT is fixed to local CPU int8")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 300:
            raise ValueError("STT timeout must be in (0, 300]")
        if self.retain_audio and self.retained_audio_directory is None:
            raise ValueError("retained_audio_directory is required when retaining audio")


class FasterWhisperSubprocessSTT:
    """Runs faster-whisper out of process with local model files only."""

    def __init__(self, config: FasterWhisperConfig):
        self.config = config

    @property
    def identity(self) -> str:
        return f"faster-whisper:{self.config.model}:cpu-int8"

    def transcribe(self, audio: CapturedAudio) -> TranscriptionResult:
        path: Path | None = None
        try:
            if self.config.retain_audio:
                directory = self.config.retained_audio_directory
                assert directory is not None
                directory.mkdir(parents=True, exist_ok=True)
                handle = tempfile.NamedTemporaryFile(prefix="graci-", suffix=".wav", dir=directory,
                                                     delete=False)
            else:
                handle = tempfile.NamedTemporaryFile(prefix="graci-", suffix=".wav", delete=False)
            path = Path(handle.name)
            handle.close()
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(audio.channels)
                wav.setsampwidth(audio.sample_width)
                wav.setframerate(audio.sample_rate)
                wav.writeframes(audio.pcm)
            command = [str(self.config.python_executable), str(self.config.worker_script),
                       "--audio", str(path), "--model", self.config.model,
                       "--cache", str(self.config.model_cache), "--device", self.config.device,
                       "--compute-type", self.config.compute_type]
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=self.config.timeout_seconds, check=False)
            if completed.returncode != 0:
                message = completed.stderr.strip() or "local STT worker failed"
                return self._failure(audio, "stt_worker_failed", message[:500])
            try:
                payload = json.loads(completed.stdout)
                text = payload["text"].strip()
            except (json.JSONDecodeError, KeyError, AttributeError) as exc:
                return self._failure(audio, "invalid_stt_response", str(exc))
            if not text:
                return self._failure(audio, "empty_transcript", "STT produced no transcript")
            return TranscriptionResult(TranscriptionStatus.SUCCESS, self.identity,
                                       audio.duration_seconds, text=text)
        except subprocess.TimeoutExpired:
            return self._failure(audio, "stt_timeout", "local STT worker timed out")
        except OSError as exc:
            return self._failure(audio, "stt_unavailable", str(exc))
        finally:
            if path is not None and not self.config.retain_audio:
                path.unlink(missing_ok=True)

    def _failure(self, audio: CapturedAudio, code: str, message: str) -> TranscriptionResult:
        return TranscriptionResult(TranscriptionStatus.FAILED, self.identity,
                                   audio.duration_seconds, error_code=code,
                                   error_message=message)
