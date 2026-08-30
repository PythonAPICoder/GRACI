"""Bounded, read-only local hardware observations for the resident visualizer.

This module never influences routing or eligibility. The local 3090 is sampled from
the fixed ``nvidia-smi`` query plus Windows native CPU/RAM counters. The optional
4090 observation comes only from the fixed, read-only telemetry client.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .visualizer import HardwareTelemetryView, TelemetryState
from .remote_telemetry import Remote4090TelemetryClient


TELEMETRY_INTERVAL_SECONDS = 2.0
NVIDIA_QUERY_TIMEOUT_SECONDS = 2.0
NVIDIA_FIELDS = (
    "name,utilization.gpu,memory.used,memory.total,temperature.gpu"
)


class LocalHardwareTelemetryCollector:
    """Collect presentation-only facts without adding control or network authority."""

    def __init__(self, *, runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
                 clock: Callable[[], datetime] | None = None,
                 optional_client: Remote4090TelemetryClient | None = None):
        self._runner = runner or subprocess.run
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._previous_cpu: tuple[int, int, int] | None = None
        self._optional_client = optional_client or Remote4090TelemetryClient()

    def sample_primary(self) -> HardwareTelemetryView:
        observed_at = self._clock()
        gpu, gpu_reason = self._sample_3090_gpu()
        cpu, ram_used, ram_total = self._sample_windows_system()
        measurements = {
            **gpu,
            "cpu_utilization_percent": cpu,
            "cpu_temperature_c": None,
            "ram_used_mib": ram_used,
            "ram_total_mib": ram_total,
        }
        if not any(value is not None for value in measurements.values()):
            return HardwareTelemetryView(
                TelemetryState.UNAVAILABLE, reason=gpu_reason or "local_telemetry_unavailable")
        sources = []
        if gpu:
            sources.append("nvidia-smi")
        if ram_total is not None:
            sources.append("windows-native")
        return HardwareTelemetryView(
            TelemetryState.OBSERVED, observed_at, "+".join(sources),
            reason=gpu_reason, **measurements)

    @staticmethod
    def optional_unavailable() -> HardwareTelemetryView:
        return HardwareTelemetryView(
            TelemetryState.UNAVAILABLE,
            reason="no_authorized_read_only_4090_telemetry_source")

    def sample_optional(self) -> HardwareTelemetryView:
        """Read display-only 4090 telemetry; never return policy authority."""
        return self._optional_client.sample()

    def _sample_3090_gpu(self) -> tuple[dict[str, float | int | None], str | None]:
        executable = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "nvidia-smi.exe"
        if not executable.is_file():
            return {}, "nvidia_smi_unavailable"
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = self._runner(
                [str(executable), f"--query-gpu={NVIDIA_FIELDS}",
                 "--format=csv,noheader,nounits"],
                text=True, capture_output=True, timeout=NVIDIA_QUERY_TIMEOUT_SECONDS,
                check=False, creationflags=creation_flags)
        except (OSError, subprocess.SubprocessError):
            return {}, "nvidia_smi_failed"
        if result.returncode != 0:
            return {}, "nvidia_smi_failed"
        for line in result.stdout.splitlines():
            values = [item.strip() for item in line.split(",")]
            if len(values) != 5 or "RTX 3090" not in values[0].upper():
                continue
            try:
                return {
                    "gpu_utilization_percent": float(values[1]),
                    "vram_used_mib": int(float(values[2])),
                    "vram_total_mib": int(float(values[3])),
                    "gpu_temperature_c": float(values[4]),
                }, None
            except ValueError:
                return {}, "nvidia_smi_malformed"
        return {}, "rtx_3090_not_observed"

    def _sample_windows_system(self) -> tuple[float | None, int | None, int | None]:
        if os.name != "nt":
            return None, None, None
        try:
            idle, kernel, user = _system_times()
            total_bytes, available_bytes = _memory_status()
        except OSError:
            return None, None, None
        cpu = None
        if self._previous_cpu is not None:
            old_idle, old_kernel, old_user = self._previous_cpu
            idle_delta = idle - old_idle
            total_delta = (kernel - old_kernel) + (user - old_user)
            if total_delta > 0:
                cpu = round(max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0)), 1)
        self._previous_cpu = (idle, kernel, user)
        mib = 1024 * 1024
        total_mib = int(total_bytes // mib)
        used_mib = int((total_bytes - available_bytes) // mib)
        return cpu, used_mib, total_mib


def _filetime_value(value: ctypes.c_void_p) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def _system_times() -> tuple[int, int, int]:
    from ctypes import wintypes
    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        raise OSError("GetSystemTimes failed")
    return _filetime_value(idle), _filetime_value(kernel), _filetime_value(user)


def _memory_status() -> tuple[int, int]:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("GlobalMemoryStatusEx failed")
    return int(status.ullTotalPhys), int(status.ullAvailPhys)
