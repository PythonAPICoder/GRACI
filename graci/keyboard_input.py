"""Small Windows-local keyboard boundary for one hold-to-talk speech turn."""

from __future__ import annotations

import ctypes
import sys
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
    def next_event(self) -> KeyEvent: ...


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

    def next_event(self) -> KeyEvent:
        while True:
            pressed = bool(self._get_async_key_state(VK_SPACE) & 0x8000)
            if pressed != self._last_pressed:
                self._last_pressed = pressed
                return KeyEvent(VK_SPACE, pressed)
            time.sleep(self._poll_interval_seconds)


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
        try:
            while True:
                result = self.handle_event(self._keyboard.next_event(), coordinator,
                                           present_speech=present_speech)
                if result is not None:
                    return result
        finally:
            if self._capture_active:
                self._capture_active = False
                coordinator.cancel_speech_turn()
