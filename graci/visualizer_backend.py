"""Loopback visualizer transport with one narrow resident-owned browser PTT path."""

from __future__ import annotations

import json
import logging
import socket
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Final, TYPE_CHECKING
from urllib.parse import unquote, urlsplit

from .visualizer import (
    EVENT_SCHEMA_VERSION, RECENT_EVENT_LIMIT, SNAPSHOT_SCHEMA_VERSION,
    RecentEventBuffer, VisualizerEvent, VisualizerSnapshot, serialize_visualizer,
)

if TYPE_CHECKING:
    from .browser_ptt import BrowserPTTOperator

API_VERSION: Final[int] = 1
DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 8766
MAX_LIVE_CLIENTS: Final[int] = 8
MAX_REQUEST_TARGET: Final[int] = 2048
SSE_HEARTBEAT_SECONDS: Final[float] = 15.0
BASE_PATH: Final[str] = "/graci/visualizer/v1"
STATIC_ROOT: Final[Path] = Path(__file__).with_name("visualizer_ui")
STATIC_ASSETS: Final[dict[str, tuple[str, str]]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/visualizer.css": ("visualizer.css", "text/css; charset=utf-8"),
    "/visualizer.js": ("visualizer.js", "text/javascript; charset=utf-8"),
}
MAX_STATIC_FILE_BYTES: Final[int] = 512_000
MAX_CONTROL_JSON_BYTES: Final[int] = 512
CONTENT_SECURITY_POLICY: Final[str] = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'none'"
)

_LOG = logging.getLogger(__name__)


class VisualizerStateProvider:
    """Thread-safe trusted publication boundary; it has no network-facing mutators."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._snapshot: VisualizerSnapshot | None = None
        self._events = RecentEventBuffer()
        self._revision = 0

    def publish_snapshot(self, snapshot: VisualizerSnapshot) -> None:
        if not isinstance(snapshot, VisualizerSnapshot):
            raise TypeError("snapshot must be a VisualizerSnapshot")
        with self._condition:
            self._snapshot = snapshot
            self._revision += 1
            self._condition.notify_all()

    def publish_event(self, event: VisualizerEvent, *, observed_at: datetime | None = None) -> None:
        if not isinstance(event, VisualizerEvent):
            raise TypeError("event must be a VisualizerEvent")
        observed = observed_at or datetime.now(timezone.utc)
        with self._condition:
            self._events = self._events.append(event, observed_at=observed)
            self._revision += 1
            self._condition.notify_all()

    def snapshot(self) -> VisualizerSnapshot | None:
        with self._condition:
            return self._snapshot

    def events(self) -> tuple[VisualizerEvent, ...]:
        with self._condition:
            return self._events.events

    def revision(self) -> int:
        with self._condition:
            return self._revision

    def wait_for_change(self, revision: int, timeout: float) -> int:
        with self._condition:
            self._condition.wait_for(lambda: self._revision != revision, timeout)
            return self._revision


class _BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address: tuple[str, int], provider: VisualizerStateProvider,
                 max_live_clients: int, heartbeat_seconds: float,
                 browser_ptt: BrowserPTTOperator | None,
                 restart_runtime: Callable[[], None] | None):
        self.provider = provider
        self.max_live_clients = max_live_clients
        self.heartbeat_seconds = heartbeat_seconds
        self.live_lock = threading.Lock()
        self.live_clients = 0
        self.stopping = threading.Event()
        self.browser_ptt = browser_ptt
        self.restart_runtime = restart_runtime
        self.restart_lock = threading.Lock()
        super().__init__(address, _Handler, bind_and_activate=True)

    def acquire_live_client(self) -> bool:
        with self.live_lock:
            if self.live_clients >= self.max_live_clients:
                return False
            self.live_clients += 1
            return True

    def release_live_client(self) -> None:
        with self.live_lock:
            self.live_clients -= 1


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "GRACI-Visualizer/1"
    sys_version = ""

    @property
    def app(self) -> _BoundedHTTPServer:
        return self.server  # type: ignore[return-value]

    def log_message(self, format: str, *args: object) -> None:
        _LOG.info("local request completed: %s", str(args[1]) if len(args) > 1 else "unknown")

    def _safe_headers(self, content_type: str, length: int | None = None) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        if length is not None:
            self.send_header("Content-Length", str(length))

    def _error(self, status: HTTPStatus, code: str, message: str) -> None:
        body = json.dumps({"error": {"code": code, "message": message}, "status": status.value},
                          sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._safe_headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.close_connection = True

    def _valid_host(self) -> bool:
        host = self.headers.get("Host", "")
        port = self.app.server_address[1]
        return host in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _request_path(self) -> str | None:
        if len(self.path) > MAX_REQUEST_TARGET:
            self._error(HTTPStatus.REQUEST_URI_TOO_LONG, "request_target_too_long", "request target is too long")
            return None
        if not self._valid_host():
            self._error(HTTPStatus.BAD_REQUEST, "invalid_host", "Host must match the local visualizer")
            return None
        target = urlsplit(self.path)
        try:
            decoded_path = unquote(target.path, errors="strict")
        except (UnicodeDecodeError, ValueError):
            decoded_path = ".."
        if (target.query or target.fragment or "\\" in decoded_path or
                "//" in decoded_path or ".." in decoded_path or "\x00" in decoded_path):
            self._error(HTTPStatus.BAD_REQUEST, "invalid_request_target", "query and malformed paths are not accepted")
            return None
        return decoded_path

    def _same_origin_loopback(self) -> bool:
        if self.client_address[0] not in {"127.0.0.1", "::1"}:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin == f"http://{self.headers.get('Host', '')}"

    def _content_length(self, maximum: int) -> int | None:
        if self.headers.get("Transfer-Encoding") is not None:
            self._error(HTTPStatus.BAD_REQUEST, "transfer_encoding_rejected",
                        "streamed request bodies are not accepted")
            return None
        raw = self.headers.get("Content-Length")
        try:
            length = int(raw) if raw is not None else -1
        except ValueError:
            length = -1
        if length < 0:
            self._error(HTTPStatus.LENGTH_REQUIRED, "content_length_required",
                        "a valid Content-Length is required")
            return None
        if length > maximum:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request_too_large",
                        "request body exceeds the push-to-talk limit")
            return None
        return length

    def do_HEAD(self) -> None:
        self._read(head_only=True)

    def do_GET(self) -> None:
        self._read(head_only=False)

    def _read(self, *, head_only: bool) -> None:
        path = self._request_path()
        if path is None:
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length != 0 or self.headers.get("Transfer-Encoding") is not None:
            self._error(HTTPStatus.BAD_REQUEST, "request_body_rejected", "request bodies are not accepted")
            return
        if path == f"{BASE_PATH}/health":
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            self._json({"api_version": API_VERSION, "event_schema_version": EVENT_SCHEMA_VERSION,
                        "generated_at": now, "service_status": "ok",
                        "snapshot_available": self.app.provider.snapshot() is not None,
                        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION}, head_only)
        elif path == f"{BASE_PATH}/snapshot":
            snapshot = self.app.provider.snapshot()
            if snapshot is None:
                self._error(HTTPStatus.SERVICE_UNAVAILABLE, "snapshot_unavailable", "no runtime snapshot has been published")
            else:
                self._serialized(serialize_visualizer(snapshot), head_only)
        elif path == f"{BASE_PATH}/events":
            payload = "[" + ",".join(serialize_visualizer(item) for item in self.app.provider.events()) + "]"
            self._serialized(payload, head_only)
        elif path == f"{BASE_PATH}/events/stream" and not head_only:
            last_id = self.headers.get("Last-Event-ID")
            if last_id is not None and (not last_id or len(last_id) > 128 or
                                        any(ord(c) < 33 or ord(c) > 126 for c in last_id)):
                self._error(HTTPStatus.BAD_REQUEST, "invalid_last_event_id",
                            "Last-Event-ID is invalid")
            else:
                self._stream(last_id)
        elif path == f"{BASE_PATH}/events/stream":
            self.send_response(HTTPStatus.OK)
            self._safe_headers("text/event-stream; charset=utf-8", 0)
            self.end_headers()
        elif path in STATIC_ASSETS:
            self._static(path, head_only)
        else:
            self._error(HTTPStatus.NOT_FOUND, "not_found", "visualizer endpoint not found")

    def _static(self, path: str, head_only: bool) -> None:
        filename, content_type = STATIC_ASSETS[path]
        asset = STATIC_ROOT / filename
        try:
            body = asset.read_bytes()
        except OSError:
            self._error(HTTPStatus.NOT_FOUND, "asset_unavailable", "visualizer asset unavailable")
            return
        if len(body) > MAX_STATIC_FILE_BYTES:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "asset_too_large", "visualizer asset exceeds bound")
            return
        self.send_response(HTTPStatus.OK)
        self._safe_headers(content_type, len(body))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _json(self, value: dict[str, object], head_only: bool) -> None:
        self._serialized(json.dumps(value, sort_keys=True, separators=(",", ":")), head_only)

    def _serialized(self, value: str, head_only: bool) -> None:
        body = value.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self._safe_headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_POST(self) -> None:
        path = self._request_path()
        if path is None:
            return
        if not self._same_origin_loopback():
            self._error(HTTPStatus.FORBIDDEN, "loopback_origin_required",
                        "browser PTT is available only to the local visualizer origin")
            return
        allowed = {f"{BASE_PATH}/ptt/begin", f"{BASE_PATH}/ptt/chunk", f"{BASE_PATH}/ptt/finish",
                   f"{BASE_PATH}/ptt/cancel", f"{BASE_PATH}/restart"}
        if path not in allowed:
            self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed",
                        "POST is accepted only for explicit local operator controls")
            return
        if path == f"{BASE_PATH}/restart":
            self._restart()
            return
        if self.app.browser_ptt is None:
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "browser_ptt_unavailable",
                        "browser push-to-talk is not configured")
            return
        if path == f"{BASE_PATH}/ptt/begin":
            self._ptt_begin()
        elif path == f"{BASE_PATH}/ptt/chunk":
            self._ptt_chunk()
        elif path == f"{BASE_PATH}/ptt/finish":
            self._ptt_finish()
        elif path == f"{BASE_PATH}/ptt/cancel":
            self._ptt_cancel()

    def _restart(self) -> None:
        if self.app.restart_runtime is None:
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "restart_unavailable",
                        "runtime restart is unavailable")
            return
        if self.headers.get("Content-Type") != "application/json":
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "invalid_content_type",
                        "restart requires application/json")
            return
        length = self._content_length(MAX_CONTROL_JSON_BYTES)
        if length is None:
            return
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = None
        if value != {}:
            self._error(HTTPStatus.BAD_REQUEST, "invalid_restart_request",
                        "restart request must be an empty object")
            return
        if not self.app.restart_lock.acquire(blocking=False):
            self._json({"status": "restart_in_progress"}, False)
            return
        try:
            self.app.restart_runtime()
        except Exception as exc:
            _LOG.exception("explicit local runtime restart failed")
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "restart_failed", str(exc)[:500])
            return
        finally:
            self.app.restart_lock.release()
        self._json({"status": "ready"}, False)

    def _ptt_begin(self) -> None:
        if self.headers.get("Content-Type") != "application/json":
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "invalid_content_type",
                        "PTT begin requires application/json")
            return
        length = self._content_length(MAX_CONTROL_JSON_BYTES)
        if length is None:
            return
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = None
        if value != {}:
            self._error(HTTPStatus.BAD_REQUEST, "invalid_begin_request",
                        "PTT begin accepts only an empty JSON object")
            return
        try:
            token = self.app.browser_ptt.begin()
        except Exception as exc:
            from .browser_ptt import BrowserPTTBusy
            if isinstance(exc, BrowserPTTBusy):
                self._error(HTTPStatus.CONFLICT, "operator_busy", str(exc))
            else:
                _LOG.exception("browser PTT begin failed")
                self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "ptt_begin_failed",
                            "browser push-to-talk could not start")
            return
        self._json({"status": "listening", "turn_token": token}, False)

    def _ptt_finish(self) -> None:
        from .browser_ptt import MAX_BROWSER_AUDIO_BYTES, BrowserPTTInvalid
        if self.headers.get("Content-Type") != "audio/wav":
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "invalid_content_type",
                        "PTT finish requires audio/wav")
            return
        length = self._content_length(MAX_BROWSER_AUDIO_BYTES)
        if length is None:
            return
        token = self.headers.get("X-GRACI-PTT-Token", "")
        try:
            result = self.app.browser_ptt.finish(token, self.rfile.read(length))
        except BrowserPTTInvalid as exc:
            self._error(HTTPStatus.CONFLICT, "invalid_or_expired_turn", str(exc))
            return
        response = (result.turn_result.authoritative_response
                    if result.turn_result is not None else None)
        if result.status.value == "accepted" and response is not None:
            self._json({"status": "ok", "response": response.text}, False)
        elif result.status.value == "failed":
            self._error(HTTPStatus.BAD_GATEWAY, result.error_code or "ptt_failed",
                        result.error_message or "browser push-to-talk failed")
        else:
            code = result.error_code or "governed_response_unavailable"
            message = result.error_message or "no validated user-facing response is available"
            self._error(HTTPStatus.UNPROCESSABLE_ENTITY, code, message)

    def _ptt_chunk(self) -> None:
        from .browser_ptt import MAX_BROWSER_AUDIO_BYTES, BrowserPTTInvalid
        if self.headers.get("Content-Type") != "audio/wav":
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "invalid_content_type",
                        "PTT chunk requires audio/wav")
            return
        length = self._content_length(MAX_BROWSER_AUDIO_BYTES)
        if length is None:
            return
        token = self.headers.get("X-GRACI-PTT-Token", "")
        try:
            accepted = self.app.browser_ptt.offer(token, self.rfile.read(length))
        except BrowserPTTInvalid as exc:
            self._error(HTTPStatus.CONFLICT, "invalid_or_expired_turn", str(exc))
            return
        self._json({"status": "transcribing" if accepted else "buffering"}, False)

    def _ptt_cancel(self) -> None:
        from .browser_ptt import BrowserPTTInvalid
        if self.headers.get("Content-Type") != "application/json":
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "invalid_content_type",
                        "PTT cancel requires application/json")
            return
        length = self._content_length(MAX_CONTROL_JSON_BYTES)
        if length is None:
            return
        try:
            value = json.loads(self.rfile.read(length))
            token = value.get("turn_token") if isinstance(value, dict) else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            token = None
        try:
            self.app.browser_ptt.cancel(token)
        except BrowserPTTInvalid as exc:
            self._error(HTTPStatus.CONFLICT, "invalid_or_expired_turn", str(exc))
            return
        self._json({"status": "cancelled"}, False)

    def _stream(self, last_id: str | None) -> None:
        if not self.app.acquire_live_client():
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "live_client_limit", "live client limit reached")
            return
        try:
            self.send_response(HTTPStatus.OK)
            self._safe_headers("text/event-stream; charset=utf-8")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            last_sent_id = last_id
            if last_id is not None:
                retained = self.app.provider.events()
                ids = [item.event_id for item in retained]
                if last_id not in ids:
                    last_sent_id = None
            revision = -1
            while not self.app.stopping.is_set():
                events = self.app.provider.events()
                ids = [item.event_id for item in events]
                start = ids.index(last_sent_id) + 1 if last_sent_id in ids else 0
                pending = events[start:]
                if pending:
                    for item in pending:
                        frame = (f"id: {item.event_id}\nevent: {item.event_type.value}\n"
                                 f"data: {serialize_visualizer(item)}\n\n").encode("utf-8")
                        self.wfile.write(frame)
                        self.wfile.flush()
                        last_sent_id = item.event_id
                else:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                revision = self.app.provider.wait_for_change(revision, self.app.heartbeat_seconds)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout):
            pass
        finally:
            self.app.release_live_client()
            self.close_connection = True

    def _reject_method(self) -> None:
        self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "only GET and HEAD are allowed")

    do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_TRACE = do_CONNECT = _reject_method


@dataclass
class VisualizerServer:
    """Controlled in-process lifecycle; shutdown is deliberately not an endpoint."""

    provider: VisualizerStateProvider
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    max_live_clients: int = MAX_LIVE_CLIENTS
    heartbeat_seconds: float = SSE_HEARTBEAT_SECONDS
    browser_ptt: BrowserPTTOperator | None = None
    restart_runtime: Callable[[], None] | None = None

    def __post_init__(self) -> None:
        if self.host != DEFAULT_HOST:
            raise ValueError("visualizer host must be 127.0.0.1")
        if not 0 <= self.port <= 65535:
            raise ValueError("invalid port")
        if not 1 <= self.max_live_clients <= MAX_LIVE_CLIENTS:
            raise ValueError("invalid live client bound")
        if self.heartbeat_seconds <= 0:
            raise ValueError("heartbeat must be positive")
        self._httpd: _BoundedHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def bound_port(self) -> int:
        if self._httpd is None:
            raise RuntimeError("server is not started")
        return self._httpd.server_address[1]

    def start(self) -> None:
        if self._httpd is not None:
            raise RuntimeError("visualizer server is already started")
        httpd = _BoundedHTTPServer((self.host, self.port), self.provider,
                                   self.max_live_clients, self.heartbeat_seconds,
                                   self.browser_ptt, self.restart_runtime)
        thread = threading.Thread(target=httpd.serve_forever, name="graci-visualizer", daemon=True)
        self._httpd, self._thread = httpd, thread
        thread.start()
        _LOG.info("visualizer started on loopback port %d", self.bound_port)

    def stop(self) -> None:
        if self._httpd is None:
            return
        httpd, thread = self._httpd, self._thread
        httpd.stopping.set()
        httpd.shutdown()
        httpd.server_close()
        if thread is not None:
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("visualizer server did not stop cleanly")
        self._httpd = self._thread = None
        _LOG.info("visualizer stopped")

    def __enter__(self) -> "VisualizerServer":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
