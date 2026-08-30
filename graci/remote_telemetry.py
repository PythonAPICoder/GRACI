"""Strict, presentation-only client for the optional 4090 telemetry agent.

This client consumes one fixed observation route. It has no write routes and its
result is never consulted by availability, routing, model, or MO2 policy.
"""

from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .visualizer import HardwareTelemetryView, TelemetryState

REMOTE_TELEMETRY_URL = "http://192.168.0.101:8767/telemetry"
REMOTE_TELEMETRY_TIMEOUT_SECONDS = 1.0
REMOTE_TELEMETRY_MAX_BYTES = 16_384
REMOTE_TELEMETRY_SCHEMA_VERSION = 1
REMOTE_TELEMETRY_MAX_AGE_SECONDS = 10.0
REMOTE_NODE_ID = "4090"


class SchemaMismatch(ValueError):
    pass


class IdentityMismatch(ValueError):
    pass


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise SchemaMismatch(f"unexpected {label} schema")
    return value


def _number(value: Any, low: float, high: float, label: str) -> float | None:
    if value is None:
        return None
    if type(value) not in {int, float} or value < low or value > high:
        raise SchemaMismatch(f"invalid {label}")
    return float(value)


def _bytes(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0 or value > 2 ** 50:
        raise SchemaMismatch(f"invalid {label}")
    return value


def _status(block: dict[str, Any], label: str) -> str:
    value = block["status"]
    if value not in {"observed", "not_observed", "unavailable"}:
        raise SchemaMismatch(f"invalid {label} status")
    reason = block["reason"]
    if reason is not None and (not isinstance(reason, str) or not 1 <= len(reason) <= 120):
        raise SchemaMismatch(f"invalid {label} reason")
    return value


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise SchemaMismatch("invalid observation timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchemaMismatch("invalid observation timestamp") from exc
    if parsed.tzinfo is None:
        raise SchemaMismatch("observation timestamp is not timezone aware")
    return parsed.astimezone(timezone.utc)


def decode_4090_telemetry(body: bytes, *, now: datetime) -> HardwareTelemetryView:
    if len(body) > REMOTE_TELEMETRY_MAX_BYTES:
        raise SchemaMismatch("response exceeds fixed bound")
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("malformed telemetry document") from exc
    top = _exact(document, {"schema_version", "node_id", "hostname", "observed_at_utc",
                            "agent", "gpu", "cpu", "ram"}, "top-level")
    if top["schema_version"] != REMOTE_TELEMETRY_SCHEMA_VERSION:
        raise SchemaMismatch("unsupported schema version")
    if top["node_id"] != REMOTE_NODE_ID:
        raise IdentityMismatch("unexpected telemetry node id")
    if not isinstance(top["hostname"], str) or not 1 <= len(top["hostname"]) <= 64:
        raise SchemaMismatch("invalid hostname")
    observed_at = _timestamp(top["observed_at_utc"])
    if (observed_at - now).total_seconds() > 2:
        raise SchemaMismatch("observation timestamp is in the future")
    agent = _exact(top["agent"], {"version", "sample_interval_seconds", "process_priority"},
                   "agent")
    if (not isinstance(agent["version"], str) or len(agent["version"]) > 24 or
            type(agent["sample_interval_seconds"]) not in {int, float} or
            not 2 <= agent["sample_interval_seconds"] <= 5 or
            agent["process_priority"] not in {"below_normal", "not_applied_windows_error",
                                               "not_applied_non_windows"}):
        raise SchemaMismatch("invalid agent metadata")
    gpu = _exact(top["gpu"], {"status", "reason", "name", "utilization_percent",
                              "vram_used_bytes", "vram_total_bytes", "temperature_c"}, "gpu")
    cpu = _exact(top["cpu"], {"status", "reason", "utilization_percent", "temperature_c"},
                 "cpu")
    ram = _exact(top["ram"], {"status", "reason", "used_bytes", "total_bytes"}, "ram")
    gpu_status, cpu_status, ram_status = _status(gpu, "gpu"), _status(cpu, "cpu"), _status(ram, "ram")
    if gpu["name"] is not None and (not isinstance(gpu["name"], str) or len(gpu["name"]) > 96):
        raise SchemaMismatch("invalid GPU name")
    if gpu_status == "observed" and (gpu["name"] is None or "RTX 4090" not in gpu["name"].upper()):
        raise IdentityMismatch("telemetry GPU is not the expected RTX 4090")
    gpu_util = _number(gpu["utilization_percent"], 0, 100, "GPU utilization")
    cpu_util = _number(cpu["utilization_percent"], 0, 100, "CPU utilization")
    gpu_temp = _number(gpu["temperature_c"], -20, 150, "GPU temperature")
    cpu_temp = _number(cpu["temperature_c"], -20, 150, "CPU temperature")
    vram_used = _bytes(gpu["vram_used_bytes"], "VRAM used")
    vram_total = _bytes(gpu["vram_total_bytes"], "VRAM total")
    ram_used = _bytes(ram["used_bytes"], "RAM used")
    ram_total = _bytes(ram["total_bytes"], "RAM total")
    for status, values, label in ((gpu_status, (gpu_util, vram_used, vram_total, gpu_temp), "gpu"),
                                  (cpu_status, (cpu_util, cpu_temp), "cpu"),
                                  (ram_status, (ram_used, ram_total), "ram")):
        if status == "observed" and not any(value is not None for value in values):
            raise SchemaMismatch(f"observed {label} has no measurements")
        if status != "observed" and any(value is not None for value in values):
            raise SchemaMismatch(f"unobserved {label} exposes measurements")
    if ((vram_used is not None and vram_total is not None and
         (vram_total == 0 or vram_used > vram_total)) or
            (ram_used is not None and ram_total is not None and
             (ram_total == 0 or ram_used > ram_total))):
        raise SchemaMismatch("used memory exceeds total memory")
    measurements = (gpu_util, vram_used, vram_total, gpu_temp, cpu_util, cpu_temp,
                    ram_used, ram_total)
    if not any(value is not None for value in measurements):
        return HardwareTelemetryView(TelemetryState.UNAVAILABLE,
                                     reason="remote_telemetry_no_observations")
    age = (now - observed_at).total_seconds()
    reason = "remote_telemetry_stale" if age > REMOTE_TELEMETRY_MAX_AGE_SECONDS else None
    mib = 1024 * 1024
    return HardwareTelemetryView(
        TelemetryState.OBSERVED, observed_at, "4090-read-only-agent/v1",
        gpu_utilization_percent=gpu_util,
        vram_used_mib=None if vram_used is None else vram_used // mib,
        vram_total_mib=None if vram_total is None else vram_total // mib,
        gpu_temperature_c=gpu_temp, cpu_utilization_percent=cpu_util,
        cpu_temperature_c=cpu_temp,
        ram_used_mib=None if ram_used is None else ram_used // mib,
        ram_total_mib=None if ram_total is None else ram_total // mib,
        reason=reason)


class Remote4090TelemetryClient:
    def __init__(self, *, transport: Callable[[Request, float], bytes] | None = None,
                 clock: Callable[[], datetime] | None = None):
        self._transport = transport or self._read
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _read(request: Request, timeout: float) -> bytes:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            if response.status != 200 or content_type != "application/json":
                raise ValueError("unexpected telemetry response")
            body = response.read(REMOTE_TELEMETRY_MAX_BYTES + 1)
        return body

    def sample(self) -> HardwareTelemetryView:
        request = Request(REMOTE_TELEMETRY_URL, headers={"Accept": "application/json"},
                          method="GET")
        try:
            body = self._transport(request, REMOTE_TELEMETRY_TIMEOUT_SECONDS)
            return decode_4090_telemetry(body, now=self._clock())
        except (TimeoutError, socket.timeout):
            return HardwareTelemetryView(TelemetryState.UNAVAILABLE,
                                         reason="remote_telemetry_timeout")
        except HTTPError:
            return HardwareTelemetryView(TelemetryState.UNAVAILABLE,
                                         reason="remote_telemetry_unreachable")
        except URLError as exc:
            reason = "remote_telemetry_timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) \
                else "remote_telemetry_unreachable"
            return HardwareTelemetryView(TelemetryState.UNAVAILABLE, reason=reason)
        except IdentityMismatch:
            return HardwareTelemetryView(TelemetryState.UNKNOWN,
                                         reason="remote_telemetry_node_identity_mismatch")
        except SchemaMismatch:
            return HardwareTelemetryView(TelemetryState.UNKNOWN,
                                         reason="remote_telemetry_schema_mismatch")
        except (OSError, ValueError, TypeError):
            return HardwareTelemetryView(TelemetryState.UNKNOWN,
                                         reason="remote_telemetry_malformed")
