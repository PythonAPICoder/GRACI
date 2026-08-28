"""Explicit push-to-talk audio capture abstractions and Windows implementation."""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from .speech import CapturedAudio


class AudioCaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioCaptureConfig:
    sample_rate: int = 16_000
    channels: int = 1
    sample_width: int = 2
    device_id: int = -1
    buffer_milliseconds: int = 100
    max_duration_seconds: float = 120.0
    minimum_duration_seconds: float = 0.15

    def __post_init__(self) -> None:
        if self.sample_rate < 8_000 or self.sample_rate > 48_000:
            raise ValueError("sample_rate must be between 8000 and 48000")
        if self.channels != 1 or self.sample_width != 2:
            raise ValueError("Phase 6B capture requires mono 16-bit PCM")
        if not 20 <= self.buffer_milliseconds <= 1000:
            raise ValueError("buffer_milliseconds must be between 20 and 1000")
        if not 0 < self.minimum_duration_seconds < self.max_duration_seconds <= 120:
            raise ValueError("invalid audio duration bounds")


class CaptureSession(Protocol):
    def stop(self) -> CapturedAudio: ...
    def cancel(self) -> None: ...


class AudioCapture(Protocol):
    def start(self, config: AudioCaptureConfig) -> CaptureSession: ...


class _WaveFormat(ctypes.Structure):
    _fields_ = [("wFormatTag", ctypes.c_ushort), ("nChannels", ctypes.c_ushort),
                ("nSamplesPerSec", ctypes.c_uint), ("nAvgBytesPerSec", ctypes.c_uint),
                ("nBlockAlign", ctypes.c_ushort), ("wBitsPerSample", ctypes.c_ushort),
                ("cbSize", ctypes.c_ushort)]


class _WaveHeader(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", ctypes.c_uint),
                ("dwBytesRecorded", ctypes.c_uint), ("dwUser", ctypes.c_size_t),
                ("dwFlags", ctypes.c_uint), ("dwLoops", ctypes.c_uint),
                ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]


class WindowsWaveInCapture:
    """Dependency-free Windows waveIn PCM capture; it never starts implicitly."""

    def start(self, config: AudioCaptureConfig) -> CaptureSession:
        if sys.platform != "win32":
            raise AudioCaptureError("Windows waveIn capture is only available on Windows")
        return _WindowsWaveInSession(config)


class _WindowsWaveInSession:
    _DONE = 0x00000001
    _MAPPER = 0xFFFFFFFF

    def __init__(self, config: AudioCaptureConfig):
        self.config = config
        self._winmm = ctypes.WinDLL("winmm")
        self._handle = ctypes.c_void_p()
        self._stopping = threading.Event()
        self._failure: AudioCaptureError | None = None
        self._chunks: list[bytes] = []
        self._buffers: list[ctypes.Array] = []
        self._headers: list[_WaveHeader] = []
        format_ = _WaveFormat(1, config.channels, config.sample_rate,
                              config.sample_rate * config.channels * config.sample_width,
                              config.channels * config.sample_width, config.sample_width * 8, 0)
        device = self._MAPPER if config.device_id == -1 else config.device_id
        result = self._winmm.waveInOpen(ctypes.byref(self._handle), device,
                                        ctypes.byref(format_), 0, 0, 0)
        if result:
            raise AudioCaptureError(f"microphone unavailable (waveInOpen={result})")
        try:
            size = config.sample_rate * config.channels * config.sample_width * config.buffer_milliseconds // 1000
            for _ in range(4):
                buffer = ctypes.create_string_buffer(size)
                header = _WaveHeader(ctypes.cast(buffer, ctypes.c_void_p), size, 0, 0, 0, 0, None, 0)
                self._check(self._winmm.waveInPrepareHeader(self._handle, ctypes.byref(header), ctypes.sizeof(header)), "prepare")
                self._check(self._winmm.waveInAddBuffer(self._handle, ctypes.byref(header), ctypes.sizeof(header)), "queue")
                self._buffers.append(buffer)
                self._headers.append(header)
            self._check(self._winmm.waveInStart(self._handle), "start")
        except Exception:
            self._close()
            raise
        self._thread = threading.Thread(target=self._collect, name="graci-wavein", daemon=True)
        self._thread.start()

    def _check(self, result: int, operation: str) -> None:
        if result:
            raise AudioCaptureError(f"audio capture {operation} failed (waveIn={result})")

    def _collect(self) -> None:
        limit = int(self.config.max_duration_seconds * self.config.sample_rate *
                    self.config.channels * self.config.sample_width)
        try:
            while not self._stopping.wait(0.01):
                for header in self._headers:
                    if header.dwFlags & self._DONE:
                        if header.dwBytesRecorded:
                            self._chunks.append(ctypes.string_at(header.lpData, header.dwBytesRecorded))
                        if sum(map(len, self._chunks)) >= limit:
                            self._stopping.set()
                            break
                        header.dwBytesRecorded = 0
                        self._check(self._winmm.waveInAddBuffer(self._handle, ctypes.byref(header), ctypes.sizeof(header)), "requeue")
        except AudioCaptureError as exc:
            self._failure = exc
            self._stopping.set()

    def stop(self) -> CapturedAudio:
        self._stopping.set()
        self._winmm.waveInStop(self._handle)
        self._winmm.waveInReset(self._handle)
        self._thread.join(timeout=2)
        for header in self._headers:
            if header.dwBytesRecorded:
                self._chunks.append(ctypes.string_at(header.lpData, header.dwBytesRecorded))
                header.dwBytesRecorded = 0
        self._close()
        if self._failure:
            raise self._failure
        return CapturedAudio(b"".join(self._chunks), self.config.sample_rate,
                             self.config.channels, self.config.sample_width)

    def cancel(self) -> None:
        self._chunks.clear()
        try:
            self.stop()
        finally:
            self._chunks.clear()

    def _close(self) -> None:
        if self._handle:
            for header in self._headers:
                self._winmm.waveInUnprepareHeader(self._handle, ctypes.byref(header), ctypes.sizeof(header))
            self._winmm.waveInClose(self._handle)
            self._handle = ctypes.c_void_p()
