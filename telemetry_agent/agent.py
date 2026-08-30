"""Small cached telemetry server with no command or write authority.

The production surface is deliberately fixed: two GET routes, one trusted LAN
client, and a versioned observation schema. Sensor work happens on a slow sampler
thread; HTTP requests only return cached JSON.
"""

from __future__ import annotations

import ctypes
import json
import os
import socket
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = 2
AGENT_VERSION = "1.0.1"
NODE_ID = "4090"
BIND_ADDRESS = "192.168.0.101"
PORT = 8767
ALLOWED_CLIENTS = frozenset({"192.168.0.100", "192.168.0.101", "127.0.0.1", "::1"})
SAMPLE_INTERVAL_SECONDS = 3.0
MAX_RESPONSE_BYTES = 16_384
EXPECTED_GPU_FRAGMENT = "RTX 4090"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class _NvmlUtilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _NvmlMemory(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong),
                ("used", ctypes.c_ulonglong)]


class NvmlGpuReader:
    """Persistent direct NVML reader; never shells out to nvidia-smi."""

    def __init__(self, library: Any | None = None):
        self._library = library
        self._handle = ctypes.c_void_p()
        self._ready = False

    def open(self) -> None:
        if self._ready:
            return
        if self._library is None:
            if os.name != "nt":
                raise OSError("NVML is supported by this package on Windows")
            path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "nvml.dll"
            self._library = ctypes.WinDLL(str(path))
        self._call("nvmlInit_v2")
        count = ctypes.c_uint()
        self._call("nvmlDeviceGetCount_v2", ctypes.byref(count))
        for index in range(count.value):
            handle = ctypes.c_void_p()
            self._call("nvmlDeviceGetHandleByIndex_v2", index, ctypes.byref(handle))
            name = self._name(handle)
            if EXPECTED_GPU_FRAGMENT in name.upper():
                self._handle = handle
                self._ready = True
                return
        self.close()
        raise OSError("expected RTX 4090 was not observed")

    def _call(self, name: str, *arguments: Any) -> None:
        result = getattr(self._library, name)(*arguments)
        if result != 0:
            raise OSError(f"NVML call {name} failed with code {result}")

    def _name(self, handle: ctypes.c_void_p) -> str:
        buffer = ctypes.create_string_buffer(96)
        self._call("nvmlDeviceGetName", handle, buffer, len(buffer))
        return buffer.value.decode("utf-8", "replace")

    def sample(self) -> dict[str, Any]:
        self.open()
        utilization = _NvmlUtilization()
        memory = _NvmlMemory()
        temperature = ctypes.c_uint()
        self._call("nvmlDeviceGetUtilizationRates", self._handle, ctypes.byref(utilization))
        self._call("nvmlDeviceGetMemoryInfo", self._handle, ctypes.byref(memory))
        self._call("nvmlDeviceGetTemperature", self._handle, 0, ctypes.byref(temperature))
        return {
            "status": "observed", "reason": None, "name": self._name(self._handle),
            "utilization_percent": int(utilization.gpu),
            "vram_used_bytes": int(memory.used), "vram_total_bytes": int(memory.total),
            "temperature_c": int(temperature.value),
        }

    def close(self) -> None:
        if self._library is not None:
            try:
                self._call("nvmlShutdown")
            except (AttributeError, OSError):
                pass
        self._ready = False


class WindowsSystemReader:
    """Read CPU load and physical memory from bounded Windows kernel APIs."""

    def __init__(self):
        self._previous_cpu: tuple[int, int, int] | None = None

    def sample(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if os.name != "nt":
            raise OSError("Windows system counters are unavailable")
        idle, kernel, user = _system_times()
        total, available = _memory_status()
        utilization = None
        if self._previous_cpu is not None:
            old_idle, old_kernel, old_user = self._previous_cpu
            idle_delta = idle - old_idle
            total_delta = kernel - old_kernel + user - old_user
            if total_delta > 0:
                utilization = round(max(0.0, min(100.0, 100 * (1 - idle_delta / total_delta))), 1)
        self._previous_cpu = (idle, kernel, user)
        cpu = {"status": "observed" if utilization is not None else "not_observed",
               "reason": None if utilization is not None else "cpu_baseline_pending",
               "utilization_percent": utilization, "temperature_c": None}
        ram = {"status": "observed", "reason": None,
               "used_bytes": int(total - available), "total_bytes": int(total)}
        return cpu, ram


def _filetime(value: Any) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def _system_times() -> tuple[int, int, int]:
    from ctypes import wintypes
    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        raise OSError("GetSystemTimes failed")
    return _filetime(idle), _filetime(kernel), _filetime(user)


def _memory_status() -> tuple[int, int]:
    class Status(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    status = Status()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("GlobalMemoryStatusEx failed")
    return int(status.ullTotalPhys), int(status.ullAvailPhys)


BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
_PRIORITY_CLASS_NAMES = {
    0x00000040: "idle",
    0x00004000: "below_normal",
    0x00000020: "normal",
    0x00008000: "above_normal",
    0x00000080: "high",
    0x00000100: "realtime",
}


def _priority_report(applied: bool, effective_class: int | None) -> dict[str, str]:
    return {
        "requested": "below_normal",
        "application_result": "applied" if applied else "failed_windows_error",
        "observed_effective": _PRIORITY_CLASS_NAMES.get(effective_class, "unknown"),
    }


def apply_below_normal_priority() -> dict[str, str]:
    if os.name != "nt":
        return {
            "requested": "below_normal",
            "application_result": "not_applied_non_windows",
            "observed_effective": "unknown",
        }
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.SetPriorityClass.restype = ctypes.c_int
        kernel32.GetPriorityClass.argtypes = [ctypes.c_void_p]
        kernel32.GetPriorityClass.restype = ctypes.c_uint32
        process = kernel32.GetCurrentProcess()
        applied = bool(kernel32.SetPriorityClass(process, BELOW_NORMAL_PRIORITY_CLASS))
        effective_class = int(kernel32.GetPriorityClass(process)) or None
        return _priority_report(applied, effective_class)
    except (AttributeError, OSError):
        return _priority_report(False, None)


class HardwareSampler:
    def __init__(self, gpu: NvmlGpuReader | None = None,
                 system: WindowsSystemReader | None = None,
                 clock: Callable[[], datetime] = utc_now):
        self.gpu = gpu or NvmlGpuReader()
        self.system = system or WindowsSystemReader()
        self.clock = clock

    def sample(self, priority: dict[str, str]) -> dict[str, Any]:
        unavailable_gpu = {"status": "unavailable", "reason": "nvml_read_failed",
                           "name": None, "utilization_percent": None,
                           "vram_used_bytes": None, "vram_total_bytes": None,
                           "temperature_c": None}
        unavailable_cpu = {"status": "unavailable", "reason": "windows_counter_read_failed",
                           "utilization_percent": None, "temperature_c": None}
        unavailable_ram = {"status": "unavailable", "reason": "windows_counter_read_failed",
                           "used_bytes": None, "total_bytes": None}
        try:
            gpu = self.gpu.sample()
        except (AttributeError, OSError, ValueError):
            gpu = unavailable_gpu
        try:
            cpu, ram = self.system.sample()
        except (AttributeError, OSError, ValueError):
            cpu, ram = unavailable_cpu, unavailable_ram
        return {
            "schema_version": SCHEMA_VERSION, "node_id": NODE_ID,
            "hostname": socket.gethostname(), "observed_at_utc": iso_utc(self.clock()),
            "agent": {
                "version": AGENT_VERSION,
                "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
                "priority_requested": priority["requested"],
                "priority_application_result": priority["application_result"],
                "priority_observed_effective": priority["observed_effective"],
            },
            "gpu": gpu, "cpu": cpu, "ram": ram,
        }

    def close(self) -> None:
        self.gpu.close()


class TelemetryCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._body: bytes | None = None
        self._observed_at: str | None = None

    def publish(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("telemetry payload exceeds fixed response bound")
        with self._lock:
            self._body, self._observed_at = body, payload["observed_at_utc"]

    def telemetry(self) -> bytes | None:
        with self._lock:
            return self._body

    def health(self) -> bytes:
        with self._lock:
            status = "ready" if self._body is not None else "starting"
            observed = self._observed_at
        return json.dumps({"schema_version": SCHEMA_VERSION, "node_id": NODE_ID,
                           "status": status, "cached_observed_at_utc": observed},
                          separators=(",", ":"), sort_keys=True).encode("utf-8")


class TelemetryWorker(threading.Thread):
    def __init__(self, cache: TelemetryCache, sampler: HardwareSampler,
                 interval: float = SAMPLE_INTERVAL_SECONDS):
        super().__init__(name="graci-4090-telemetry-sampler", daemon=True)
        self.cache, self.sampler, self.interval = cache, sampler, interval
        self.stop_event = threading.Event()

    def run(self) -> None:
        priority = apply_below_normal_priority()
        try:
            while not self.stop_event.is_set():
                self.cache.publish(self.sampler.sample(priority))
                self.stop_event.wait(self.interval)
        finally:
            self.sampler.close()


def _handler(cache: TelemetryCache, allowed_clients: frozenset[str]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GRACI-Telemetry"
        sys_version = ""

        def _send(self, status: HTTPStatus, body: bytes = b"") -> None:
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD" and body:
                self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            address = self.client_address[0].removeprefix("::ffff:")
            if address not in allowed_clients:
                self._send(HTTPStatus.FORBIDDEN, b'{"error":"client_not_allowed"}')
                return
            if self.headers.get("Content-Length") not in {None, "0"}:
                self._send(HTTPStatus.BAD_REQUEST, b'{"error":"body_not_allowed"}')
                return
            if "?" in self.path or "#" in self.path:
                self._send(HTTPStatus.BAD_REQUEST, b'{"error":"parameters_not_allowed"}')
                return
            if self.path == "/health":
                self._send(HTTPStatus.OK, cache.health())
            elif self.path == "/telemetry":
                body = cache.telemetry()
                self._send(HTTPStatus.OK if body else HTTPStatus.SERVICE_UNAVAILABLE,
                           body or b'{"error":"cache_not_ready"}')
            else:
                self._send(HTTPStatus.NOT_FOUND, b'{"error":"not_found"}')

        def do_HEAD(self) -> None:  # noqa: N802
            self._send(HTTPStatus.METHOD_NOT_ALLOWED, b'{"error":"method_not_allowed"}')

        def do_POST(self) -> None:  # noqa: N802
            self._send(HTTPStatus.METHOD_NOT_ALLOWED, b'{"error":"method_not_allowed"}')

        do_PUT = do_POST
        do_PATCH = do_POST
        do_DELETE = do_POST
        do_OPTIONS = do_POST
        do_TRACE = do_POST
        do_CONNECT = do_POST

        def log_message(self, *_: Any) -> None:
            return

    return Handler


class TelemetryHttpServer(HTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], cache: TelemetryCache,
                 allowed_clients: frozenset[str] = ALLOWED_CLIENTS):
        super().__init__(address, _handler(cache, allowed_clients))


class TelemetryAgent:
    def __init__(self, address: tuple[str, int] = (BIND_ADDRESS, PORT),
                 sampler: HardwareSampler | None = None,
                 allowed_clients: frozenset[str] = ALLOWED_CLIENTS):
        self.cache = TelemetryCache()
        self.worker = TelemetryWorker(self.cache, sampler or HardwareSampler())
        self.server = TelemetryHttpServer(address, self.cache, allowed_clients)

    def serve(self) -> None:
        self.worker.start()
        try:
            self.server.serve_forever(poll_interval=.5)
        finally:
            self.worker.stop_event.set()
            self.worker.join(timeout=SAMPLE_INTERVAL_SECONDS + 1)
            self.server.server_close()


def main() -> int:
    try:
        TelemetryAgent().serve()
    except KeyboardInterrupt:
        return 0
    return 0
