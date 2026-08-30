"""Idle, single-instance resident owner for the accepted local GRACI composition."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .hardware_telemetry import (TELEMETRY_INTERVAL_SECONDS,
                                 LocalHardwareTelemetryCollector)
from .operator_cli import OperatorComposition, build_operator_composition
from .visualizer import HardwareTelemetryView, TelemetryState

STATE_SCHEMA_VERSION = 1
OWNER = "GRACI_RESIDENT_HOST"
MODULE_MARKER = "graci.resident_host"
DEFAULT_POLL_SECONDS = 0.25


class ResidentAlreadyRunning(RuntimeError):
    """The GRACI-specific resident ownership lock is held."""


def default_runtime_directory(repository_root: Path | None = None) -> Path:
    root = repository_root or Path(__file__).resolve().parents[1]
    return root / ".runtime" / "resident-host"


class ResidentOwnership:
    """OS-held lock plus validated, GRACI-specific operator state."""

    def __init__(self, runtime_directory: Path, instance_id: str | None = None):
        self.runtime_directory = runtime_directory.resolve()
        self.instance_id = instance_id or uuid.uuid4().hex
        self.lock_path = self.runtime_directory / "host.lock"
        self.state_path = self.runtime_directory / "state.json"
        self.stop_path = self.runtime_directory / "stop-request.json"
        self._file: Any = None

    def acquire(self) -> None:
        self.runtime_directory.mkdir(parents=True, exist_ok=True)
        handle = self.lock_path.open("a+b")
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            _lock(handle)
        except OSError as exc:
            handle.close()
            raise ResidentAlreadyRunning("another GRACI resident host owns the instance") from exc
        self._file = handle
        self.stop_path.unlink(missing_ok=True)

    def publish(self, *, port: int) -> None:
        if self._file is None:
            raise RuntimeError("resident ownership is not acquired")
        record = {
            "schema_version": STATE_SCHEMA_VERSION,
            "owner": OWNER,
            "instance_id": self.instance_id,
            "pid": os.getpid(),
            "executable": str(Path(sys.executable).resolve()),
            "module": MODULE_MARKER,
            "repository_root": str(self.runtime_directory.parents[1]),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "visualizer": {"host": "127.0.0.1", "port": port},
        }
        _atomic_json(self.state_path, record)

    def stop_requested(self) -> bool:
        try:
            request = read_valid_record(self.stop_path, stop_request=True)
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        return request["instance_id"] == self.instance_id

    def release(self) -> None:
        if self._file is None:
            return
        try:
            try:
                current = read_valid_record(self.state_path)
            except (OSError, ValueError, json.JSONDecodeError):
                current = None
            if current is not None and current["instance_id"] == self.instance_id:
                self.state_path.unlink(missing_ok=True)
            self.stop_path.unlink(missing_ok=True)
        finally:
            _unlock(self._file)
            self._file.close()
            self._file = None


def read_valid_record(path: Path, *, stop_request: bool = False) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ValueError("invalid GRACI resident record schema")
    if value.get("owner") != OWNER:
        raise ValueError("invalid GRACI resident record owner")
    instance_id = value.get("instance_id")
    if not isinstance(instance_id, str) or len(instance_id) < 16 or len(instance_id) > 128:
        raise ValueError("invalid GRACI resident instance id")
    if not stop_request:
        if value.get("module") != MODULE_MARKER or not isinstance(value.get("pid"), int):
            raise ValueError("invalid GRACI resident process identity")
        visualizer = value.get("visualizer")
        if (not isinstance(visualizer, dict) or visualizer.get("host") != "127.0.0.1"
                or not isinstance(visualizer.get("port"), int)):
            raise ValueError("invalid GRACI resident visualizer identity")
    return value


def resident_is_active(runtime_directory: Path | None = None) -> bool:
    """Probe only the GRACI lock; never inspect or signal an unrelated process."""
    ownership = ResidentOwnership(runtime_directory or default_runtime_directory())
    try:
        ownership.acquire()
    except ResidentAlreadyRunning:
        return True
    ownership.release()
    return False


@dataclass
class ResidentHost:
    ownership: ResidentOwnership
    composition_factory: Callable[..., OperatorComposition] = build_operator_composition
    poll_seconds: float = DEFAULT_POLL_SECONDS
    telemetry_factory: Callable[[], LocalHardwareTelemetryCollector] = LocalHardwareTelemetryCollector

    def run(self) -> int:
        """Own the accepted runtime and observer server; submit no work."""
        self.ownership.acquire()
        composition: OperatorComposition | None = None
        server_started = False
        stopping = False

        def request_stop(*_: object) -> None:
            nonlocal stopping
            stopping = True

        previous = {}
        for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            number = getattr(signal, name, None)
            if number is not None:
                try:
                    previous[number] = signal.signal(number, request_stop)
                except (OSError, ValueError):
                    pass
        try:
            composition = self.composition_factory(visualizer=True, browser_operator=True)
            if composition.server is None or composition.runtime_observer is None:
                raise RuntimeError("resident composition requires the accepted visualizer observer")
            telemetry = self.telemetry_factory()
            self._publish_telemetry(composition, telemetry)
            last_telemetry = time.monotonic()
            composition.server.start()
            server_started = True
            self.ownership.publish(port=composition.server.bound_port)
            while not stopping and not self.ownership.stop_requested():
                time.sleep(self.poll_seconds)
                if time.monotonic() - last_telemetry >= TELEMETRY_INTERVAL_SECONDS:
                    self._publish_telemetry(composition, telemetry)
                    last_telemetry = time.monotonic()
            return 0
        finally:
            if server_started and composition is not None and composition.server is not None:
                composition.server.stop()
            if composition is not None and composition.browser_ptt is not None:
                composition.browser_ptt.close()
            self.ownership.release()
            for number, handler in previous.items():
                try:
                    signal.signal(number, handler)
                except (OSError, ValueError):
                    pass

    @staticmethod
    def _publish_telemetry(composition: OperatorComposition,
                           collector: LocalHardwareTelemetryCollector) -> None:
        try:
            primary = collector.sample_primary()
        except Exception:
            primary = HardwareTelemetryView(
                TelemetryState.UNAVAILABLE, reason="local_telemetry_collection_failed")
        try:
            optional = collector.sample_optional()
        except Exception:
            optional = HardwareTelemetryView(
                TelemetryState.UNAVAILABLE, reason="remote_telemetry_collection_failed")
        composition.runtime_observer.publish_hardware_telemetry(primary, optional)


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _lock(handle: Any) -> None:
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle: Any) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the idle local GRACI resident host")
    parser.add_argument("--runtime-directory", type=Path)
    parser.add_argument("--instance-id")
    args = parser.parse_args(argv)
    ownership = ResidentOwnership(
        args.runtime_directory or default_runtime_directory(), args.instance_id)
    try:
        return ResidentHost(ownership).run()
    except ResidentAlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
