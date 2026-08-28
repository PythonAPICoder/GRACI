"""Bounded subprocess-isolated audio playback for Phase 6D."""

from __future__ import annotations

import subprocess
import tempfile
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .tts import SynthesizedAudio


class PlaybackStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class PlaybackResult:
    status: PlaybackStatus
    error_code: str | None = None
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is PlaybackStatus.SUCCESS


@dataclass(frozen=True)
class PlaybackConfig:
    python_executable: Path
    worker_script: Path
    timeout_seconds: float = 125.0

    def __post_init__(self) -> None:
        if not 0 < self.timeout_seconds <= 130:
            raise ValueError("playback timeout must be in (0, 130]")


class SubprocessWavePlayback:
    """Allows one bounded blocking playback process and explicit stop/cancel."""

    def __init__(self, config: PlaybackConfig):
        self.config = config
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._cancel_requested = False
        self._last_cleanup_error: str | None = None

    def play(self, audio: SynthesizedAudio) -> PlaybackResult:
        self._last_cleanup_error = None
        result = self._play(audio)
        if self._last_cleanup_error is not None:
            return PlaybackResult(PlaybackStatus.FAILED, "playback_cleanup_failed",
                                  self._last_cleanup_error)
        return result

    def _play(self, audio: SynthesizedAudio) -> PlaybackResult:
        if not isinstance(audio, SynthesizedAudio):
            raise TypeError("audio must be SynthesizedAudio")
        if not self._lock.acquire(blocking=False):
            return PlaybackResult(PlaybackStatus.FAILED, "playback_busy",
                                  "one playback operation is already outstanding")
        path: Path | None = None
        try:
            self._cancel_requested = False
            with tempfile.NamedTemporaryFile(prefix="graci-playback-", suffix=".wav",
                                             delete=False) as wav_file:
                path = Path(wav_file.name)
                wav_file.write(audio.wav_bytes)
            self._process = subprocess.Popen(
                [str(self.config.python_executable), str(self.config.worker_script),
                 "--audio", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True)
            try:
                _, stderr = self._process.communicate(timeout=self.config.timeout_seconds)
            except subprocess.TimeoutExpired:
                self._terminate()
                return PlaybackResult(PlaybackStatus.TIMEOUT, "playback_timeout",
                                      "audio playback timed out")
            if self._cancel_requested:
                return PlaybackResult(PlaybackStatus.CANCELLED, "playback_cancelled",
                                      "audio playback was cancelled")
            if self._process.returncode != 0:
                return PlaybackResult(PlaybackStatus.FAILED, "playback_failed",
                                      (stderr.strip() or "audio playback failed")[:500])
            return PlaybackResult(PlaybackStatus.SUCCESS)
        except OSError as exc:
            return PlaybackResult(PlaybackStatus.FAILED, "playback_unavailable", str(exc)[:500])
        finally:
            self._process = None
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    self._last_cleanup_error = str(exc)[:500]
            self._lock.release()

    def stop(self) -> None:
        self._cancel_requested = True
        self._terminate()

    cancel = stop

    def _terminate(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
