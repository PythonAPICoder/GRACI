"""Small Windows-local keyboard boundary for one hold-to-talk speech turn."""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from .turn_coordinator import ExplicitTurnCoordinator, TurnResult


VK_SPACE = 0x20


class KeyboardInputError(RuntimeError):
    pass


@dataclass(frozen=True)
class KeyEvent:
    virtual_key: int
    pressed: bool


class KeyboardInput(Protocol):
    def next_event(self, timeout_seconds: float | None = None) -> KeyEvent | None: ...


class WindowsSpacebarInput:
    """Poll Windows key state and expose only physical Spacebar transitions."""

    def __init__(self, poll_interval_seconds: float = 0.01):
        if sys.platform != "win32":
            raise KeyboardInputError("Spacebar push-to-talk is only available on Windows")
        self._get_async_key_state = ctypes.WinDLL("user32").GetAsyncKeyState
        self._get_async_key_state.argtypes = (ctypes.c_int,)
        self._get_async_key_state.restype = ctypes.c_short
        self._poll_interval_seconds = poll_interval_seconds
        self._last_pressed = False

    def next_event(self, timeout_seconds: float | None = None) -> KeyEvent | None:
        deadline = (time.monotonic() + timeout_seconds
                    if timeout_seconds is not None else None)
        while True:
            pressed = bool(self._get_async_key_state(VK_SPACE) & 0x8000)
            if pressed != self._last_pressed:
                self._last_pressed = pressed
                return KeyEvent(VK_SPACE, pressed)
            if deadline is not None and time.monotonic() >= deadline:
                return None
            delay = self._poll_interval_seconds
            if deadline is not None:
                delay = min(delay, max(0.0, deadline - time.monotonic()))
            if delay:
                time.sleep(delay)


class HoldSpacebarToTalk:
    """Map one Spacebar hold/release to one existing coordinator speech turn."""

    def __init__(self, keyboard: KeyboardInput):
        self._keyboard = keyboard
        self._held = False
        self._capture_active = False

    def handle_event(self, event: KeyEvent, coordinator: ExplicitTurnCoordinator,
                     *, present_speech: bool = False) -> TurnResult | None:
        if event.virtual_key != VK_SPACE:
            return None
        if event.pressed:
            if self._held:
                return None
            self._held = True
            result = coordinator.begin_speech_turn()
            self._capture_active = result is None
            return result
        if not self._held:
            return None
        self._held = False
        if not self._capture_active:
            return None
        self._capture_active = False
        return coordinator.finish_speech_turn(present_speech=present_speech)

    def run(self, coordinator: ExplicitTurnCoordinator, *,
            present_speech: bool = False) -> TurnResult:
        result: TurnResult | None = None
        worker: threading.Thread | None = None

        def finish() -> None:
            nonlocal result
            result = coordinator.finish_speech_turn(present_speech=present_speech)

        try:
            while True:
                if worker is not None and not worker.is_alive() and not self._capture_active:
                    worker.join()
                    assert result is not None
                    return result
                try:
                    event = self._keyboard.next_event(.05 if worker is not None else None)
                except TypeError:
                    try:
                        event = self._keyboard.next_event()
                    except StopIteration:
                        if worker is None:
                            raise
                        worker.join()
                        assert result is not None
                        return result
                except StopIteration:
                    if worker is None:
                        raise
                    worker.join()
                    assert result is not None
                    return result
                if event is None:
                    continue
                if worker is None:
                    if (event.virtual_key == VK_SPACE and not event.pressed
                            and self._held and self._capture_active):
                        self._held = False
                        self._capture_active = False
                        worker = threading.Thread(target=finish, name="graci-cli-turn")
                        worker.start()
                    else:
                        immediate = self.handle_event(event, coordinator,
                                                      present_speech=present_speech)
                        if immediate is not None:
                            return immediate
                    continue
                if event.virtual_key != VK_SPACE:
                    continue
                if event.pressed:
                    if self._held:
                        continue
                    self._held = True
                    immediate = coordinator.begin_speech_turn()
                    self._capture_active = immediate is None
                    if immediate is not None:
                        self._held = False
                elif self._held:
                    self._held = False
                    if self._capture_active:
                        self._capture_active = False
                        worker.join()
                        result = None
                        worker = threading.Thread(target=finish, name="graci-cli-turn")
                        worker.start()
        finally:
            if self._capture_active:
                self._capture_active = False
                coordinator.cancel_speech_turn()
            if worker is not None:
                worker.join()
