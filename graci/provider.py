"""OpenAI-compatible transport for the local llama.cpp server."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .config import Config


@dataclass(frozen=True)
class ProviderResponse:
    http_status: int
    content: str
    response_model: str | None


class ProviderError(Exception):
    def __init__(self, message: str, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status


Transport = Callable[[urllib.request.Request, float], tuple[int, bytes]]


def _urlopen_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


class LocalLlamaCppProvider:
    def __init__(self, config: Config, transport: Transport = _urlopen_transport):
        self.config = config
        self.transport = transport

    def execute(self, task: str) -> ProviderResponse:
        body = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "/no_think\nReturn only one JSON object with exactly these fields: "
                        "schema_version (integer 1), status (PASS or FAIL), and summary "
                        "(a non-empty string). Do not use markdown fences. Mark PASS only "
                        "when the task was completed as requested."
                    ),
                },
                {"role": "user", "content": task},
            ],
            "temperature": 0,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        return self._request(body)

    def _send(self, request: urllib.request.Request) -> ProviderResponse:
        try:
            status, raw = self.transport(request, self.config.timeout_seconds)
        except urllib.error.HTTPError as exc:
            message = f"HTTP error {exc.code}: {exc.reason}"
            status = exc.code
            exc.close()
            raise ProviderError(message, status) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"local provider request failed: {exc}") from exc

        if status != 200:
            raise ProviderError(f"unexpected HTTP status {status}", status)
        try:
            payload: dict[str, Any] = json.loads(raw.decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            response_model = payload.get("model")
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"invalid OpenAI-compatible response envelope: {exc}", status) from exc
        if not isinstance(content, str):
            raise ProviderError("assistant content is not a string", status)
        return ProviderResponse(status, content, response_model if isinstance(response_model, str) else None)

    def propose_text_action(self, task: str, allowed_target: str) -> ProviderResponse:
        """Ask the fixed local model for one bounded text-file action."""
        body = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "/no_think\nReturn only one JSON object with exactly these fields: "
                        "schema_version (integer 1), action (string write_text), target_path "
                        "(the exact allowed relative path supplied below), content (string), and "
                        "rationale (a concise non-empty string). Do not use markdown fences. "
                        "You propose an action only; GRACI independently validates, executes, "
                        "and verifies it. Allowed target path: " + allowed_target
                    ),
                },
                {"role": "user", "content": task},
            ],
            "temperature": 0,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        return self._request(body)

    def _request(self, body: dict[str, Any]) -> ProviderResponse:
        request = urllib.request.Request(
            self.config.endpoint.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._send(request)
