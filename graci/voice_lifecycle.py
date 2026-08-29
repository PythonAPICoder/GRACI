"""Observer-only publication of bounded voice activity."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from .visualizer import SystemState


_LOG = logging.getLogger(__name__)
_VOICE_STATES = frozenset((SystemState.LISTENING, SystemState.SPEAKING))


@dataclass(frozen=True)
class VoiceLifecycleEvent:
    sequence: int
    state: SystemState
    timestamp: datetime


class VoiceLifecycleObserver(Protocol):
    def publish(self, event: VoiceLifecycleEvent) -> None: ...


class VoiceLifecycleLease:
    """Idempotent ownership token preventing late restoration of newer activity."""

    def __init__(self, lifecycle: "VoiceLifecycle", generation: int, active: bool):
        self._lifecycle = lifecycle
        self._generation = generation
        self.active = active
        self._closed = False

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self.active:
                self._lifecycle._restore(self._generation)

    def __enter__(self) -> "VoiceLifecycleLease":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


class VoiceLifecycle:
    """Canonical, non-authoritative voice state with a replaceable observer."""

    def __init__(self, observer: VoiceLifecycleObserver | None = None):
        self._observer = observer
        self._state = SystemState.IDLE
        self._sequence = 0
        self._generation = 0
        self._lock = threading.RLock()
        self._publication_failures: list[str] = []

    @property
    def state(self) -> SystemState:
        with self._lock:
            return self._state

    @property
    def publication_failures(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._publication_failures)

    def reset(self) -> None:
        """Invalidate transient leases and return the voice surface to rest."""
        with self._lock:
            self._generation += 1
            if self._state is not SystemState.IDLE:
                self._set_and_publish(SystemState.IDLE)

    def enter(self, state: SystemState) -> VoiceLifecycleLease:
        if state not in _VOICE_STATES:
            raise ValueError("voice activity must be listening or speaking")
        with self._lock:
            if self._state is not SystemState.IDLE:
                _LOG.warning("voice lifecycle transition rejected: %s -> %s",
                             self._state.value, state.value)
                return VoiceLifecycleLease(self, self._generation, False)
            self._generation += 1
            generation = self._generation
            self._set_and_publish(state)
            return VoiceLifecycleLease(self, generation, True)

    def enter_listening(
        self, interrupt_speaking: Callable[[], None] | None = None,
    ) -> VoiceLifecycleLease:
        """Enter LISTENING, allowing only an explicit owned-playback interruption."""
        with self._lock:
            if self._state is not SystemState.SPEAKING:
                return self.enter(SystemState.LISTENING)
            if interrupt_speaking is None:
                return VoiceLifecycleLease(self, self._generation, False)
            speaking_generation = self._generation

        # Playback termination may wait for the playback thread, whose finally block
        # closes its lease. Never hold the lifecycle lock across that bounded wait.
        interrupt_speaking()

        with self._lock:
            if self._generation != speaking_generation:
                return VoiceLifecycleLease(self, self._generation, False)
            if self._state not in (SystemState.SPEAKING, SystemState.IDLE):
                return VoiceLifecycleLease(self, self._generation, False)
            self._generation += 1  # invalidate the interrupted SPEAKING lease
            generation = self._generation
            self._set_and_publish(SystemState.LISTENING)
            return VoiceLifecycleLease(self, generation, True)

    def _restore(self, generation: int) -> None:
        with self._lock:
            if generation != self._generation or self._state not in _VOICE_STATES:
                return
            self._set_and_publish(SystemState.IDLE)

    def _set_and_publish(self, state: SystemState) -> None:
        self._state = state
        self._sequence += 1
        event = VoiceLifecycleEvent(self._sequence, state, datetime.now(timezone.utc))
        if self._observer is None:
            return
        try:
            self._observer.publish(event)
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"[:500]
            self._publication_failures.append(failure)
            _LOG.warning("voice lifecycle publisher failed (%s)", failure)
