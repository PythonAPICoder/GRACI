"""Read-only Phase 8D probes, reduction service, and bounded resident lifecycle evidence."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .availability import Mo2State, check_4090_mo2_status, evaluate_4090_eligibility
from .registry import (
    GLM_MODEL_ID, OPTIONAL_ENDPOINT_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID,
    HealthState, apply_health_result, build_phase3a_registry,
    check_openai_models_endpoint,
)
from .runtime_context import (
    ComponentReadiness, ComponentState, ReadinessState, RuntimeReadiness,
    StartupStage, reduce_readiness,
)


HEALTH_INTERVAL_SECONDS = 10.0
LIFECYCLE_HEARTBEAT_SECONDS = 30.0
LIFECYCLE_SCHEMA_VERSION = 1
MAX_LIFECYCLE_BYTES = 256_000
MAX_LIFECYCLE_RECORDS = 400
RESIDENT_TASK_NAME = "GRACI Resident Host"
ROUTER_TASK_NAME = "GRACI 3090 llama.cpp Router"


@dataclass(frozen=True)
class ScheduledTaskObservation:
    state: str
    reason: str
    enabled: bool | None = None
    scheduler_state: str | None = None
    last_result: int | None = None
    last_run_time: str | None = None


TaskProbe = Callable[[str], ScheduledTaskObservation]
EndpointProbe = Callable[[str, float], tuple[bool, str]]
ModelStateTransport = Callable[[urllib.request.Request, float], tuple[int, bytes]]


def probe_windows_scheduled_task(name: str) -> ScheduledTaskObservation:
    """Read one exact root task and preserve access-denied versus missing."""
    if sys.platform != "win32":
        return ScheduledTaskObservation("unknown", "scheduled_tasks_require_windows")
    script = r"""
$ErrorActionPreference = 'Stop'
try {
  $task = Get-ScheduledTask -TaskPath '\' -TaskName $env:GRACI_HEALTH_TASK_NAME -ErrorAction Stop
  $info = Get-ScheduledTaskInfo -InputObject $task -ErrorAction Stop
  [pscustomobject]@{
    kind='task'; enabled=[bool]$task.Settings.Enabled; state=[string]$task.State
    last_result=[int64]$info.LastTaskResult
    last_run_time=if($info.LastRunTime -eq [datetime]::MinValue){$null}else{$info.LastRunTime.ToString('o')}
  } | ConvertTo-Json -Compress
} catch {
  [pscustomobject]@{
    kind='error'; category=[string]$_.CategoryInfo.Category
    error_id=[string]$_.FullyQualifiedErrorId; message=[string]$_.Exception.Message
  } | ConvertTo-Json -Compress
  exit 3
}
"""
    environment = os.environ.copy()
    environment["GRACI_HEALTH_TASK_NAME"] = name
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            text=True, capture_output=True, timeout=4, check=False, env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ScheduledTaskObservation("unknown", f"task_query_failed:{type(exc).__name__}")
    line = next((item for item in reversed(result.stdout.splitlines()) if item.strip()), "")
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return ScheduledTaskObservation("unknown", "task_query_returned_invalid_evidence")
    if payload.get("kind") == "task":
        last_result = payload.get("last_result")
        return ScheduledTaskObservation(
            "registered", "exact_root_task_registered",
            bool(payload.get("enabled")), str(payload.get("state") or "Unknown"),
            last_result if type(last_result) is int else None,
            payload.get("last_run_time") if isinstance(payload.get("last_run_time"), str) else None,
        )
    category = str(payload.get("category") or "")
    error_id = str(payload.get("error_id") or "")
    message = str(payload.get("message") or "")
    combined = f"{category} {error_id} {message}".lower()
    if "access denied" in combined or category in {"PermissionDenied", "SecurityError"}:
        return ScheduledTaskObservation("access_denied_unknown", "task_enumeration_access_denied")
    if (category == "ObjectNotFound" or "nomatchingscheduledtask" in combined or
            "no matching" in combined or "cannot find" in combined):
        return ScheduledTaskObservation("missing", "exact_root_task_not_found")
    return ScheduledTaskObservation("unknown", "task_enumeration_failed_unknown")


def probe_http_runtime(url: str, timeout_seconds: float) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(4097)
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        return False, f"runtime_http_error:{status}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"runtime_request_failure:{type(exc).__name__}"
    if status != 200 or len(raw) > 4096:
        return False, "runtime_response_invalid"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, "runtime_response_invalid"
    if not isinstance(payload, dict) or payload.get("api_version") != 1:
        return False, "runtime_identity_mismatch"
    suffix = "/graci/visualizer/v1/health"
    if not url.endswith(suffix):
        return False, "runtime_health_url_invalid"
    browser_url = url[:-len(suffix)] + "/"
    browser_request = urllib.request.Request(
        browser_url, method="GET", headers={"Accept": "text/html"})
    try:
        with urllib.request.urlopen(browser_request, timeout=timeout_seconds) as response:
            browser = response.read(512_001)
            browser_status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        return False, f"browser_http_error:{status}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"browser_request_failure:{type(exc).__name__}"
    if (browser_status != 200 or len(browser) > 512_000 or
            b"<title>G.R.A.C.I. Visualizer</title>" not in browser):
        return False, "browser_runtime_response_invalid"
    return True, "loopback_runtime_and_browser_responded"


def probe_openai_model_states(base_url: str, *, timeout_seconds: float = 1.5,
                              transport: ModelStateTransport | None = None
                              ) -> dict[str, str]:
    """Read bounded llama.cpp lifecycle labels without changing the shared registry schema."""
    request = urllib.request.Request(base_url.rstrip("/") + "/models", method="GET")
    try:
        if transport is None:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                status, raw = response.status, response.read(65_537)
        else:
            status, raw = transport(request, timeout_seconds)
    except urllib.error.HTTPError as exc:
        exc.close()
        return {}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {}
    if status != 200 or len(raw) > 65_536:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return {}
    states: dict[str, str] = {}
    for item in payload["data"][:16]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        state = item.get("status")
        if isinstance(state, dict):
            state = state.get("value")
        if isinstance(state, str) and 0 < len(state) <= 80:
            states[item["id"]] = state
    return states


class RuntimeHealthCollector:
    """Collect fixed local/read-only facts; it has no repair or execution methods."""

    def __init__(self, repository_root: Path, *, task_probe: TaskProbe = probe_windows_scheduled_task,
                 endpoint_probe: EndpointProbe = probe_http_runtime,
                 clock: Callable[[], datetime] | None = None):
        self.root = repository_root.resolve()
        self.task_probe = task_probe
        self.endpoint_probe = endpoint_probe
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def collect(self, *, include_resident: bool,
                resident_endpoint_url: str | None = None,
                previous_state: ReadinessState | None = None) -> RuntimeReadiness:
        observed_at = self.clock()
        local_now = observed_at.astimezone()
        components: list[ComponentReadiness] = [ComponentReadiness(
            "trusted_clock", True, ComponentState.READY, observed_at,
            "timezone_aware_operating_system_clock_observed",
            facts=(("timezone", str(local_now.tzname() or "unknown")),),
        )]
        registry = build_phase3a_registry()
        with ThreadPoolExecutor(max_workers=6, thread_name_prefix="graci-health") as pool:
            resident_task_future = pool.submit(
                self._task_component, "resident_scheduled_task", RESIDENT_TASK_NAME,
                observed_at)
            router_task_future = pool.submit(
                self._task_component, "router_scheduled_task", ROUTER_TASK_NAME,
                observed_at)
            primary_future = pool.submit(
                check_openai_models_endpoint,
                registry.endpoints[PRIMARY_ENDPOINT_ID], timeout_seconds=1.5)
            primary_states_future = pool.submit(
                probe_openai_model_states,
                registry.endpoints[PRIMARY_ENDPOINT_ID].base_url, timeout_seconds=1.5)
            optional_future = pool.submit(
                check_openai_models_endpoint,
                registry.endpoints[OPTIONAL_ENDPOINT_ID], timeout_seconds=1.5)
            mo2_future = pool.submit(check_4090_mo2_status, timeout_seconds=1.5)
            resident_task = resident_task_future.result()
            router_task = router_task_future.result()
            primary_result = primary_future.result()
            primary_states = primary_states_future.result()
            optional_result = optional_future.result()
            mo2 = mo2_future.result()
        components.extend((resident_task, router_task))
        observed_models = set(primary_result.observed_models)
        components.append(ComponentReadiness(
            "router_endpoint", True,
            ComponentState.READY if primary_result.state is HealthState.HEALTHY
            else ComponentState.UNAVAILABLE,
            observed_at, primary_result.reason,
            StartupStage.RUNTIME_READY if primary_result.state is HealthState.HEALTHY else None,
            (("http_status", primary_result.http_status),),
        ))
        components.append(self._model_component(
            "qwen_model", QWEN_MODEL_ID, True, observed_models, primary_states, observed_at))
        components.append(self._model_component(
            "glm_model", GLM_MODEL_ID, False, observed_models, primary_states, observed_at))

        registry = registry.with_endpoint(apply_health_result(
            registry.endpoints[OPTIONAL_ENDPOINT_ID], optional_result))
        components.append(ComponentReadiness(
            "optional_4090_endpoint", False,
            ComponentState.READY if optional_result.state is HealthState.HEALTHY
            else ComponentState.UNAVAILABLE,
            observed_at, optional_result.reason,
            StartupStage.RUNTIME_READY if optional_result.state is HealthState.HEALTHY else None,
            (("models_observed", len(optional_result.observed_models)),),
        ))
        mo2_state = (ComponentState.READY if mo2.state is Mo2State.NOT_RUNNING else
                     ComponentState.BLOCKED if mo2.state is Mo2State.RUNNING else
                     ComponentState.UNKNOWN)
        components.append(ComponentReadiness(
            "optional_4090_mo2", False, mo2_state, observed_at, mo2.reason_code,
            facts=(("state", mo2.state.value),),
        ))
        eligibility = evaluate_4090_eligibility(registry, QWEN_MODEL_ID, mo2)
        components.append(ComponentReadiness(
            "optional_4090_eligibility", False,
            ComponentState.READY if eligibility.eligible else ComponentState.BLOCKED,
            observed_at, eligibility.reason_code.value,
            facts=(("eligible", eligibility.eligible),),
        ))
        components.extend((self._stt_resources(observed_at), self._tts_resources(observed_at)))

        if include_resident:
            components.append(ComponentReadiness(
                "resident_process", True, ComponentState.READY, observed_at,
                "owned_resident_process_is_collecting_health",
                StartupStage.PROCESS_ALIVE,
                (("pid", os.getpid()),),
            ))
            if resident_endpoint_url is None:
                components.append(ComponentReadiness(
                    "resident_runtime", True, ComponentState.DEGRADED, observed_at,
                    "resident_loopback_runtime_not_yet_probed",
                ))
            else:
                ready, reason = self.endpoint_probe(resident_endpoint_url, 1.5)
                components.append(ComponentReadiness(
                    "resident_runtime", True,
                    ComponentState.READY if ready else ComponentState.UNAVAILABLE,
                    observed_at, reason,
                    StartupStage.RUNTIME_READY if ready else None,
                ))
        return reduce_readiness(tuple(components), observed_at=observed_at,
                                local_now=local_now, previous_state=previous_state)

    def _task_component(self, component_id: str, name: str,
                        observed_at: datetime) -> ComponentReadiness:
        item = self.task_probe(name)
        if item.state == "missing":
            return ComponentReadiness(component_id, True, ComponentState.DEGRADED,
                                      observed_at, item.reason, StartupStage.MISSING)
        if item.state == "access_denied_unknown":
            return ComponentReadiness(component_id, True, ComponentState.UNKNOWN,
                                      observed_at, item.reason,
                                      StartupStage.ACCESS_DENIED_UNKNOWN)
        if item.state != "registered":
            return ComponentReadiness(component_id, True, ComponentState.UNKNOWN,
                                      observed_at, item.reason)
        stage = (StartupStage.LAUNCHER_SUCCEEDED if item.last_result == 0 and item.last_run_time
                 else StartupStage.REGISTERED)
        state = (ComponentState.READY if item.enabled and stage is StartupStage.LAUNCHER_SUCCEEDED
                 else ComponentState.DEGRADED)
        return ComponentReadiness(
            component_id, True, state, observed_at, item.reason, stage,
            (("enabled", item.enabled), ("last_result", item.last_result),
             ("last_run_time", item.last_run_time), ("scheduler_state", item.scheduler_state)),
        )

    @staticmethod
    def _model_component(component_id: str, model_id: str, required: bool,
                         observed: set[str], model_states: dict[str, str],
                         at: datetime) -> ComponentReadiness:
        available = model_id in observed
        return ComponentReadiness(
            component_id, required,
            ComponentState.READY if available else ComponentState.UNAVAILABLE,
            at, "model_reported_by_router" if available else "model_absent_from_router",
            facts=(("load_state", model_states.get(model_id, "unknown")),
                   ("model_id", model_id)),
        )

    def _stt_resources(self, at: datetime) -> ComponentReadiness:
        paths = (
            self.root / "phase6a/.venv/Scripts/python.exe",
            self.root / "phase6b/stt_worker.py",
            self.root / "phase6a/cache/huggingface",
        )
        return self._resource_component("stt_resources", paths, at)

    def _tts_resources(self, at: datetime) -> ComponentReadiness:
        paths = (
            self.root / "phase6a/.venv312/Scripts/python.exe",
            self.root / "phase6d/tts_worker.py",
            self.root / "phase6a/cache/kokoro-onnx/kokoro-v1.0.int8.onnx",
            self.root / "phase6a/cache/kokoro-onnx/voices-v1.0.bin",
        )
        return self._resource_component("tts_resources", paths, at)

    @staticmethod
    def _resource_component(component_id: str, paths: tuple[Path, ...],
                            at: datetime) -> ComponentReadiness:
        missing = sum(not path.exists() for path in paths)
        return ComponentReadiness(
            component_id, True,
            ComponentState.READY if missing == 0 else ComponentState.DEGRADED,
            at, "required_local_runtime_assets_present" if missing == 0
            else "required_local_runtime_assets_missing",
            facts=(("asset_count", len(paths)), ("missing_count", missing)),
        )


class RuntimeHealthService:
    def __init__(self, collector: RuntimeHealthCollector):
        self.collector = collector
        self._lock = threading.RLock()
        self._latest: RuntimeReadiness | None = None

    def sample(self, *, include_resident: bool,
               resident_endpoint_url: str | None = None) -> RuntimeReadiness:
        with self._lock:
            previous = self._latest.state if self._latest is not None else None
        value = self.collector.collect(
            include_resident=include_resident,
            resident_endpoint_url=resident_endpoint_url,
            previous_state=previous,
        )
        with self._lock:
            self._latest = value
        return value

    def latest(self) -> RuntimeReadiness | None:
        with self._lock:
            return self._latest

    def prompt_context(self) -> dict[str, object] | None:
        value = self.latest()
        if value is None:
            try:
                value = self.sample(include_resident=False)
            except Exception:
                return None
        return value.prompt_context() if value is not None else None


class ResidentLifecycleLedger:
    """Bounded JSONL evidence; absence of a clean exit remains diagnostically visible."""

    def __init__(self, path: Path, *, clock: Callable[[], datetime] | None = None):
        self.path = path
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()

    def begin(self, instance_id: str) -> None:
        previous = self._last_record()
        if (previous is not None and previous.get("instance_id") != instance_id and
                previous.get("event") not in {"resident_stopped", "resident_failed"}):
            self.append(instance_id, "previous_resident_exit_unrecorded",
                        reason="prior_lifecycle_ended_without_terminal_event")
        self.append(instance_id, "resident_starting")

    def append(self, instance_id: str, event: str, *,
               readiness: RuntimeReadiness | None = None,
               reason: str | None = None) -> None:
        if event not in {"previous_resident_exit_unrecorded", "resident_starting",
                         "launcher_published", "readiness_changed", "resident_heartbeat",
                         "resident_stopped", "resident_failed"}:
            raise ValueError("unsupported resident lifecycle event")
        record: dict[str, object] = {
            "schema_version": LIFECYCLE_SCHEMA_VERSION,
            "timestamp": self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "instance_id": instance_id,
            "event": event,
        }
        if readiness is not None:
            record.update({"readiness": readiness.state.value,
                           "readiness_observed_at": readiness.observed_at.astimezone(
                               timezone.utc).isoformat().replace("+00:00", "Z")})
            record["components"] = [
                {"id": item.component_id, "state": item.state.value,
                 "reason": item.reason,
                 "startup_stage": (item.startup_stage.value
                                   if item.startup_stage is not None else None)}
                for item in readiness.components
                if item.state is not ComponentState.READY or item.startup_stage is not None
            ]
        if reason is not None:
            record["reason"] = " ".join(reason.split())[:240]
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
            self._trim()

    def _last_record(self) -> dict[str, object] | None:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        for line in reversed(lines[-MAX_LIFECYCLE_RECORDS:]):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("schema_version") == LIFECYCLE_SCHEMA_VERSION:
                return value
        return None

    def _trim(self) -> None:
        try:
            if self.path.stat().st_size <= MAX_LIFECYCLE_BYTES:
                return
            lines = self.path.read_text(encoding="utf-8").splitlines()
            retained = lines[-MAX_LIFECYCLE_RECORDS:]
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text("\n".join(retained) + "\n", encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            return
