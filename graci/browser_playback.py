"""Bounded, single-owner browser presentation for authorized synthesized audio."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from enum import Enum

from .playback import PlaybackResult, PlaybackStatus
from .tts import SynthesizedAudio
from .visualizer import SystemState
from .voice_lifecycle import VoiceLifecycle, VoiceLifecycleLease

CLAIM_SECONDS = 12.0
PLAYBACK_GRACE_SECONDS = 5.0
ARTIFACT_SECONDS = 150.0
TOKEN_BYTES = 24


class BrowserPlaybackError(RuntimeError):
    pass


class ArtifactState(str, Enum):
    AVAILABLE = "available"
    CLAIMED = "claimed"
    PLAYING = "playing"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    ERROR = "error"
    EXPIRED = "expired"


@dataclass
class _Artifact:
    artifact_id: str
    audio: SynthesizedAudio
    created: float
    state: ArtifactState = ArtifactState.AVAILABLE
    client_id: str | None = None
    claim_token: str | None = None
    claim_deadline: float | None = None
    terminal_code: str | None = None


class BrowserPlaybackBroker:
    """Player contract backed only by accepted in-memory SynthesizedAudio objects."""

    manages_lifecycle = True

    def __init__(self, lifecycle: VoiceLifecycle | None = None, *, clock=time.monotonic,
                 claim_seconds: float = CLAIM_SECONDS):
        self._clock = clock
        self._claim_seconds = claim_seconds
        self._condition = threading.Condition()
        self._active: _Artifact | None = None
        self._lifecycle = lifecycle
        self._lease: VoiceLifecycleLease | None = None

    def play(self, audio: SynthesizedAudio) -> PlaybackResult:
        if not isinstance(audio, SynthesizedAudio):
            raise TypeError("audio must be SynthesizedAudio")
        with self._condition:
            self._expire_locked()
            if self._active is not None and self._active.state not in _TERMINAL:
                return PlaybackResult(PlaybackStatus.FAILED, "playback_busy",
                                      "one browser playback artifact is already active")
            artifact = _Artifact(secrets.token_urlsafe(TOKEN_BYTES), audio, self._clock())
            self._active = artifact
            deadline = artifact.created + min(ARTIFACT_SECONDS,
                                               audio.duration_seconds + CLAIM_SECONDS + PLAYBACK_GRACE_SECONDS)
            while artifact.state not in _TERMINAL:
                remaining = deadline - self._clock()
                if remaining <= 0:
                    artifact.state = ArtifactState.EXPIRED
                    artifact.terminal_code = "playback_claim_timeout"
                    break
                self._condition.wait(min(remaining, .5))
                self._expire_locked()
            state, code = artifact.state, artifact.terminal_code
            if self._active is artifact:
                self._active = None
            self._close_lease_locked()
            if state is ArtifactState.COMPLETE:
                return PlaybackResult(PlaybackStatus.SUCCESS)
            if state is ArtifactState.CANCELLED:
                return PlaybackResult(PlaybackStatus.CANCELLED, code or "playback_cancelled",
                                      "browser playback was cancelled")
            status = PlaybackStatus.TIMEOUT if state is ArtifactState.EXPIRED else PlaybackStatus.FAILED
            return PlaybackResult(status, code or "browser_playback_failed",
                                  "browser presentation did not complete")

    def available(self) -> dict[str, object] | None:
        with self._condition:
            self._expire_locked()
            artifact = self._active
            if artifact is None or artifact.state is not ArtifactState.AVAILABLE:
                return None
            return {"artifact_id": artifact.artifact_id,
                    "duration_seconds": artifact.audio.duration_seconds}

    def claim(self, artifact_id: str, client_id: str) -> dict[str, str]:
        _validate_opaque(artifact_id, "artifact")
        _validate_opaque(client_id, "client")
        with self._condition:
            self._expire_locked()
            artifact = self._require(artifact_id)
            if artifact.state is not ArtifactState.AVAILABLE:
                raise BrowserPlaybackError("speech artifact is not available")
            artifact.state = ArtifactState.CLAIMED
            artifact.client_id = client_id
            artifact.claim_token = secrets.token_urlsafe(TOKEN_BYTES)
            artifact.claim_deadline = self._clock() + self._claim_seconds
            return {"artifact_id": artifact.artifact_id,
                    "claim_token": artifact.claim_token}

    def audio(self, artifact_id: str, claim_token: str) -> bytes:
        with self._condition:
            artifact = self._authorized(artifact_id, claim_token)
            if artifact.state not in {ArtifactState.CLAIMED, ArtifactState.PLAYING}:
                raise BrowserPlaybackError("speech artifact is no longer playable")
            return artifact.audio.wav_bytes

    def acknowledge(self, artifact_id: str, claim_token: str, event: str,
                    error_code: str | None = None) -> None:
        with self._condition:
            artifact = self._authorized(artifact_id, claim_token)
            if event == "started" and artifact.state is ArtifactState.CLAIMED:
                if self._lifecycle is not None:
                    self._lease = self._lifecycle.enter(SystemState.SPEAKING)
                artifact.state = ArtifactState.PLAYING
                artifact.claim_deadline = self._clock() + artifact.audio.duration_seconds + PLAYBACK_GRACE_SECONDS
            elif event == "completed" and artifact.state is ArtifactState.PLAYING:
                artifact.state = ArtifactState.COMPLETE
            elif event in {"cancelled", "error"} and artifact.state in {
                    ArtifactState.CLAIMED, ArtifactState.PLAYING}:
                artifact.state = (ArtifactState.CANCELLED if event == "cancelled"
                                  else ArtifactState.ERROR)
                artifact.terminal_code = (error_code or f"playback_{event}")[:100]
            else:
                raise BrowserPlaybackError("stale or invalid playback acknowledgement")
            if artifact.state in _TERMINAL:
                self._close_lease_locked()
            self._condition.notify_all()

    def stop(self) -> None:
        with self._condition:
            artifact = self._active
            if artifact is not None and artifact.state not in _TERMINAL:
                artifact.state = ArtifactState.CANCELLED
                artifact.terminal_code = "playback_cancelled"
                self._close_lease_locked()
                self._condition.notify_all()

    cancel = stop

    def _expire_locked(self) -> None:
        artifact = self._active
        if (artifact is not None and artifact.state in {ArtifactState.CLAIMED, ArtifactState.PLAYING}
                and artifact.claim_deadline is not None
                and self._clock() >= artifact.claim_deadline):
            artifact.state = ArtifactState.EXPIRED
            artifact.terminal_code = "playback_claim_expired"
            self._close_lease_locked()
            self._condition.notify_all()

    def _close_lease_locked(self) -> None:
        if self._lease is not None:
            self._lease.close()
            self._lease = None

    def _require(self, artifact_id: str) -> _Artifact:
        artifact = self._active
        if artifact is None or not secrets.compare_digest(artifact.artifact_id, artifact_id):
            raise BrowserPlaybackError("invalid or expired speech artifact")
        return artifact

    def _authorized(self, artifact_id: str, claim_token: str) -> _Artifact:
        _validate_opaque(claim_token, "claim")
        artifact = self._require(artifact_id)
        if artifact.claim_token is None or not secrets.compare_digest(artifact.claim_token, claim_token):
            raise BrowserPlaybackError("invalid or expired speech claim")
        self._expire_locked()
        return artifact


_TERMINAL = {ArtifactState.COMPLETE, ArtifactState.CANCELLED,
             ArtifactState.ERROR, ArtifactState.EXPIRED}


def _validate_opaque(value: str, label: str) -> None:
    if not isinstance(value, str) or not 20 <= len(value) <= 128 or not value.replace("-", "").replace("_", "").isalnum():
        raise BrowserPlaybackError(f"invalid {label} identifier")
