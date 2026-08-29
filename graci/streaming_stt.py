"""Transient local incremental STT with release-gated finalization."""

from __future__ import annotations

import hashlib
import threading

from .speech import CapturedAudio, SpeechToText, TranscriptionResult

FINALIZE_PREVIEW_WAIT_SECONDS = 1.0


class DeferredStreamingTranscriber:
    """Run latest-only rolling snapshots; expose only a post-release final result."""

    def __init__(self, stt: SpeechToText, *, minimum_seconds: float = 0.5):
        self._source_stt = stt
        self._stt = stt
        self._owns_stt = False
        self._minimum_seconds = minimum_seconds
        self._condition = threading.Condition()
        self._pending: CapturedAudio | None = None
        self._generation = 0
        self._closed = False
        self._last_digest: bytes | None = None
        self._last_result: TranscriptionResult | None = None
        self._worker = threading.Thread(target=self._run, name="graci-incremental-stt",
                                        daemon=True)
        self._worker.start()

    def offer(self, audio: CapturedAudio) -> bool:
        """Queue a transient snapshot, replacing any snapshot not yet started."""
        if audio.duration_seconds < self._minimum_seconds:
            return False
        with self._condition:
            if self._closed:
                return False
            self._pending = self._bounded_preview(audio)
            self._condition.notify()
        return True

    def finalize(self, audio: CapturedAudio) -> TranscriptionResult:
        """Close incremental work and authoritatively transcribe released audio once."""
        digest = self._digest(audio)
        self._close(discard=False, wait=True)
        try:
            if self._last_digest == digest and self._last_result is not None:
                return self._last_result
            return self._ensure_stt().transcribe(audio)
        finally:
            self._close_stt()

    def cancel(self) -> None:
        """Discard every transient snapshot/result without producing final text."""
        self._close(discard=True, wait=False)
        self._close_stt()

    def _close(self, *, discard: bool, wait: bool) -> None:
        with self._condition:
            self._closed = True
            self._pending = None
            self._generation += 1
            if discard:
                self._last_digest = self._last_result = None
            self._condition.notify_all()
        if wait:
            self._worker.join(timeout=FINALIZE_PREVIEW_WAIT_SECONDS)
            if self._worker.is_alive():
                # An obsolete preview must not hold release behind the STT timeout.
                self._close_stt()
                self._worker.join(timeout=2)
        if discard:
            self._last_digest = self._last_result = None

    def _run(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._pending is not None or self._closed)
                if self._pending is None:
                    return
                audio, self._pending, generation = self._pending, None, self._generation
            try:
                stt = self._ensure_stt()
                with self._condition:
                    if self._closed:
                        self._close_stt()
                        return
                result = stt.transcribe(audio)
            except Exception:
                continue
            with self._condition:
                if not self._closed and generation == self._generation:
                    self._last_digest = self._digest(audio)
                    self._last_result = result

    def _close_stt(self) -> None:
        if self._owns_stt:
            self._owns_stt = False
            close = getattr(self._stt, "close")
            close()

    def _ensure_stt(self) -> SpeechToText:
        if not self._owns_stt:
            open_stream = getattr(self._source_stt, "open_stream", None)
            if open_stream is not None:
                self._stt = open_stream()
                self._owns_stt = True
        return self._stt

    @staticmethod
    def _bounded_preview(audio: CapturedAudio) -> CapturedAudio:
        maximum = 3 * audio.sample_rate * audio.channels * audio.sample_width
        pcm = audio.pcm[-maximum:]
        return CapturedAudio(pcm, audio.sample_rate, audio.channels, audio.sample_width)

    @staticmethod
    def _digest(audio: CapturedAudio) -> bytes:
        metadata = f"{audio.sample_rate}:{audio.channels}:{audio.sample_width}:".encode()
        return hashlib.sha256(metadata + audio.pcm).digest()
