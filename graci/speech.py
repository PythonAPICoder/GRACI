"""Typed, local-only speech input primitives for Phase 6B."""

from __future__ import annotations

import json
import queue
import subprocess
import tempfile
import threading
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


class StreamingSpeechToText(SpeechToText, Protocol):
    def close(self) -> None: ...


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

    def open_stream(self) -> StreamingSpeechToText:
        """Start one turn-scoped worker which loads the local model exactly once."""
        return _FasterWhisperWorkerSession(self)

    def _failure(self, audio: CapturedAudio, code: str, message: str) -> TranscriptionResult:
        return TranscriptionResult(TranscriptionStatus.FAILED, self.identity,
                                   audio.duration_seconds, error_code=code,
                                   error_message=message)


class _FasterWhisperWorkerSession:
    def __init__(self, owner: FasterWhisperSubprocessSTT):
        self._owner = owner
        config = owner.config
        command = [str(config.python_executable), str(config.worker_script), "--serve",
                   "--model", config.model, "--cache", str(config.model_cache),
                   "--device", config.device, "--compute-type", config.compute_type]
        self._process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         text=True, bufsize=1)
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._reader = threading.Thread(target=self._read_stdout,
                                        name="graci-stt-worker-reader", daemon=True)
        self._reader.start()
        try:
            ready = self._responses.get(timeout=config.timeout_seconds)
            if ready is None or json.loads(ready).get("status") != "ready":
                self.close()
                raise OSError("local streaming STT worker did not become ready")
        except (queue.Empty, json.JSONDecodeError, AttributeError):
            self.close()
            raise OSError("local streaming STT worker did not become ready") from None
        self._lock = threading.Lock()

    @property
    def identity(self) -> str:
        return self._owner.identity

    def transcribe(self, audio: CapturedAudio) -> TranscriptionResult:
        path: Path | None = None
        try:
            handle = tempfile.NamedTemporaryFile(prefix="graci-stream-", suffix=".wav",
                                                 delete=False)
            path = Path(handle.name)
            handle.close()
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(audio.channels)
                wav.setsampwidth(audio.sample_width)
                wav.setframerate(audio.sample_rate)
                wav.writeframes(audio.pcm)
            with self._lock:
                if self._process.poll() is not None or self._process.stdin is None:
                    return self._owner._failure(audio, "stt_worker_failed",
                                                "local streaming STT worker stopped")
                self._process.stdin.write(json.dumps({"audio": str(path)}) + "\n")
                self._process.stdin.flush()
                line = self._responses.get(timeout=self._owner.config.timeout_seconds)
            if line is None:
                return self._owner._failure(audio, "stt_worker_failed",
                                            "local streaming STT worker stopped")
            payload = json.loads(line)
            if "error" in payload:
                return self._owner._failure(audio, "stt_worker_failed", str(payload["error"]))
            text = payload["text"].strip()
            if not text:
                return self._owner._failure(audio, "empty_transcript",
                                            "STT produced no transcript")
            return TranscriptionResult(TranscriptionStatus.SUCCESS, self.identity,
                                       audio.duration_seconds, text=text)
        except queue.Empty:
            self.close()
            return self._owner._failure(audio, "stt_timeout", "local STT worker timed out")
        except (OSError, json.JSONDecodeError, KeyError, AttributeError) as exc:
            return self._owner._failure(audio, "stt_worker_failed", str(exc))
        finally:
            if path is not None:
                path.unlink(missing_ok=True)

    def close(self) -> None:
        process = self._process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    def _read_stdout(self) -> None:
        stdout = self._process.stdout
        if stdout is not None:
            for line in stdout:
                self._responses.put(line)
        self._responses.put(None)
