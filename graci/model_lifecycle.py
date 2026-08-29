"""Bounded model leases for the authoritative llama.cpp router on the 3090."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

from .registry import GLM_MODEL_ID, QWEN_MODEL_ID


APPROVED_PRIMARY_MODELS = frozenset({QWEN_MODEL_ID, GLM_MODEL_ID})


class ModelLifecycleError(RuntimeError):
    """The requested approved local model could not be made ready."""


LifecycleTransport = Callable[[urllib.request.Request, float], tuple[int, bytes]]


def _transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


@dataclass(frozen=True)
class ModelReadiness:
    model: str
    status: str


class PrimaryModelLifecycle:
    """Serialize router model selection and inference within this GRACI process.

    The llama.cpp router is configured separately with ``--models-max 1``.  Holding
    this lease through inference prevents one GRACI request from evicting the model
    used by another request.  llama.cpp independently serializes its child lifecycle.
    """

    def __init__(self, base_url: str, *, timeout_seconds: float = 120.0,
                 poll_interval_seconds: float = 0.25,
                 transport: LifecycleTransport = _transport,
                 monotonic: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        if timeout_seconds <= 0 or poll_interval_seconds <= 0:
            raise ValueError("model lifecycle timeouts must be positive")
        self.base_url = base_url.rstrip("/")
        self.router_url = (self.base_url[:-3] if self.base_url.endswith("/v1")
                           else self.base_url)
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.transport = transport
        self.monotonic = monotonic
        self.sleep = sleep
        self._lock = threading.Lock()
        self._process_lock_path = os.path.join(tempfile.gettempdir(),
                                               "graci-3090-model-router.lock")

    @contextmanager
    def lease(self, model: str) -> Iterator[ModelReadiness]:
        if model not in APPROVED_PRIMARY_MODELS:
            raise ModelLifecycleError(f"unapproved primary model: {model!r}")
        with self._lock:
            with self._process_lock():
                readiness = self._ensure_ready(model)
                yield readiness

    @contextmanager
    def _process_lock(self) -> Iterator[None]:
        """Bounded cross-process lock; the file contains no authority or state."""
        handle = open(self._process_lock_path, "a+b")
        handle.seek(0)
        if handle.tell() == 0 and os.path.getsize(self._process_lock_path) == 0:
            handle.write(b"0")
            handle.flush()
        deadline = self.monotonic() + self.timeout_seconds
        acquired = False
        try:
            while not acquired:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:  # pragma: no cover - exercised on non-Windows hosts
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError:
                    if self.monotonic() >= deadline:
                        raise ModelLifecycleError("timed out acquiring primary model lease")
                    self.sleep(self.poll_interval_seconds)
            yield
        finally:
            if acquired:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def _request(self, path: str, *, body: dict[str, str] | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        url = self.base_url + "/models" if path == "/models" else self.router_url + path
        request = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method="POST" if data else "GET")
        try:
            status, raw = self.transport(request, min(5.0, self.timeout_seconds))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ModelLifecycleError(
                f"primary llama.cpp lifecycle request failed: {type(exc).__name__}") from exc
        if status != 200:
            raise ModelLifecycleError(f"primary llama.cpp lifecycle HTTP status {status}")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelLifecycleError("primary llama.cpp lifecycle returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise ModelLifecycleError("primary llama.cpp lifecycle returned a non-object")
        return payload

    @staticmethod
    def _model_status(payload: dict, requested: str) -> str | None:
        data = payload.get("data")
        if not isinstance(data, list):
            raise ModelLifecycleError("primary /models response has no model list")
        matches = [item for item in data if isinstance(item, dict) and item.get("id") == requested]
        if len(matches) != 1:
            return None
        status = matches[0].get("status")
        if not isinstance(status, dict) or not isinstance(status.get("value"), str):
            return None
        if status.get("failed") is True:
            error = matches[0].get("error") or "model child failed"
            raise ModelLifecycleError(f"primary model {requested!r} failed: {error}")
        return status["value"]

    def _ensure_ready(self, model: str) -> ModelReadiness:
        initial = self._request("/models")
        status = self._model_status(initial, model)
        if status is None:
            raise ModelLifecycleError(
                f"primary /models does not expose router status for {model!r}")
        if status != "loaded":
            response = self._request("/models/load", body={"model": model})
            if response.get("success") is not True:
                raise ModelLifecycleError(f"primary model load was rejected for {model!r}")

        deadline = self.monotonic() + self.timeout_seconds
        while True:
            payload = self._request("/models")
            status = self._model_status(payload, model)
            if status == "loaded":
                return ModelReadiness(model, status)
            if status is None:
                raise ModelLifecycleError(
                    f"primary /models stopped reporting requested model {model!r}")
            if self.monotonic() >= deadline:
                raise ModelLifecycleError(
                    f"timed out waiting for primary model {model!r}; last status {status!r}")
            self.sleep(self.poll_interval_seconds)
