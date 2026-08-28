"""Phase 3D deterministic optional-node placement and bounded failover."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .availability import (Mo2StatusResult, check_4090_mo2_status,
                           evaluate_4090_eligibility)
from .registry import (LOCAL_PROVIDER_ID, OPTIONAL_ENDPOINT_ID, OPTIONAL_NODE_ID,
                       HealthResult, ModelRole, Registry, apply_health_result,
                       check_openai_models_endpoint)
from .routing import Phase3BRoleRouter, RoleBinding
from .observation import ObservationKind, observe


ELIGIBILITY_MAX_AGE_SECONDS = 10.0


class DistributedRoutingError(RuntimeError):
    """Raised only after every bounded authorized attempt fails."""

    def __init__(self, message: str, evidence: dict[str, Any]):
        super().__init__(message)
        self.evidence = evidence


@dataclass(frozen=True)
class RoutedResponse:
    content: str
    response_model: str | None
    node_id: str
    evidence: dict[str, Any]


InferenceTransport = Callable[[urllib.request.Request, float], tuple[int, bytes]]
Mo2Check = Callable[[], Mo2StatusResult]
HealthCheck = Callable[[Any, tuple[str, ...]], HealthResult]
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _age_seconds(checked_at: str, now: datetime) -> float | None:
    try:
        checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        if checked.tzinfo is None:
            return None
        age = (now - checked.astimezone(timezone.utc)).total_seconds()
        return age if age >= 0 else None
    except (TypeError, ValueError):
        return None


def _default_inference_transport(request: urllib.request.Request,
                                 timeout: float) -> tuple[int, bytes]:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


class Phase3DDistributedRouter:
    """Keep role selection fixed and place explicitly preferred work deterministically."""

    def __init__(self, registry: Registry, *, run_directory: Path = Path("runs"),
                 max_eligibility_age_seconds: float = ELIGIBILITY_MAX_AGE_SECONDS,
                 timeout_seconds: float = 120.0,
                 mo2_check: Mo2Check | None = None,
                 health_check: HealthCheck | None = None,
                 inference_transport: InferenceTransport = _default_inference_transport,
                 clock: Clock = _utc_now, observer: Any = None):
        if max_eligibility_age_seconds <= 0 or timeout_seconds <= 0:
            raise ValueError("freshness and inference timeouts must be positive")
        self.registry = registry
        self.run_directory = Path(run_directory)
        self.max_age = max_eligibility_age_seconds
        self.timeout = timeout_seconds
        self.mo2_check = mo2_check or (lambda: check_4090_mo2_status(timeout_seconds=3.0))
        self.health_check = health_check or (
            lambda endpoint, models: check_openai_models_endpoint(
                endpoint, timeout_seconds=3.0))
        self.inference_transport = inference_transport
        self.clock = clock
        self.observer = observer

    def route(self, role: ModelRole | str, prompt: str, *,
              prefer_optional: bool = False) -> RoutedResponse:
        """Perform no more than one optional attempt and one primary attempt."""
        started = self.clock()
        primary_binding = Phase3BRoleRouter(self.registry).resolve(role)
        record: dict[str, Any] = {
            "schema_version": 1, "phase": "3D", "run_id": str(uuid.uuid4()),
            "started_at": _stamp(started), "ended_at": None,
            "routing_policy": "explicit_optional_else_primary",
            "optional_requested": bool(prefer_optional),
            "logical_role": primary_binding.role.value,
            "selected_model": primary_binding.model,
            "provider": LOCAL_PROVIDER_ID, "cloud_ai_used": False,
            "eligibility": None, "attempts": [],
            "contacted_4090_chat_completions": False,
            "contacted_3090_chat_completions": False,
            "contact_counts": {"4090_chat_completions": 0,
                               "3090_chat_completions": 0},
            "fallback_occurred": False, "fallback_reason": None,
            "final_node": None, "final_endpoint": None,
            "actual_server_model": None, "final_outcome": "FAIL",
        }
        candidates: list[RoleBinding] = []
        if prefer_optional:
            remote = self._fresh_optional_binding(primary_binding, record)
            if remote is not None:
                candidates.append(remote)
            else:
                record["fallback_occurred"] = True
                record["fallback_reason"] = record["eligibility"]["reason_code"]
        candidates.append(primary_binding)

        last_error = "no authorized endpoint"
        for index, binding in enumerate(candidates):
            contacted_key = ("contacted_4090_chat_completions" if
                             binding.node_id == OPTIONAL_NODE_ID else
                             "contacted_3090_chat_completions")
            record[contacted_key] = True
            count_key = ("4090_chat_completions" if
                         binding.node_id == OPTIONAL_NODE_ID else
                         "3090_chat_completions")
            record["contact_counts"][count_key] += 1
            attempt = {"attempt": index + 1, "node_id": binding.node_id,
                       "endpoint_id": binding.endpoint_id, "endpoint": binding.endpoint,
                       "model": binding.model, "status": "ERROR", "http_status": None,
                       "response_model": None, "error": None}
            record["attempts"].append(attempt)
            try:
                response = self._infer(binding, prompt)
                attempt.update(status="SUCCESS", http_status=response[0],
                               response_model=response[2])
                record.update(final_node=binding.node_id, final_endpoint=binding.endpoint,
                              actual_server_model=response[2], final_outcome="SUCCESS",
                              ended_at=_stamp(self.clock()))
                self._persist(record)
                observe(self.observer, ObservationKind.ROUTE_COMPLETED, record["run_id"],
                        role=record["logical_role"], model=record["selected_model"],
                        node=record["final_node"], optional_requested=record["optional_requested"],
                        fallback=record["fallback_occurred"], eligibility=record["eligibility"],
                        success=True)
                return RoutedResponse(response[1], response[2], binding.node_id, record)
            except RuntimeError as exc:  # converted to bounded truthful routing evidence
                last_error = f"{type(exc).__name__}: {exc}"
                attempt["error"] = last_error
                if binding.node_id == OPTIONAL_NODE_ID:
                    record["fallback_occurred"] = True
                    record["fallback_reason"] = "4090_inference_failure"
                    continue
                break
        record["ended_at"] = _stamp(self.clock())
        self._persist(record)
        observe(self.observer, ObservationKind.ROUTE_COMPLETED, record["run_id"],
                role=record["logical_role"], model=record["selected_model"], node=None,
                optional_requested=record["optional_requested"], fallback=record["fallback_occurred"],
                eligibility=record["eligibility"], success=False)
        raise DistributedRoutingError(last_error, record)

    def _fresh_optional_binding(self, primary: RoleBinding,
                                record: dict[str, Any]) -> RoleBinding | None:
        mo2 = self.mo2_check()
        remote_endpoint = self.registry.endpoints[OPTIONAL_ENDPOINT_ID]
        health = self.health_check(remote_endpoint, (primary.model,))
        checked_registry = self.registry.with_endpoint(apply_health_result(remote_endpoint, health))
        decision = evaluate_4090_eligibility(checked_registry, primary.model, mo2)
        now = self.clock()
        mo2_age = _age_seconds(mo2.checked_at, now)
        health_age = _age_seconds(health.checked_at, now)
        fresh = (mo2_age is not None and health_age is not None and
                 mo2_age <= self.max_age and health_age <= self.max_age)
        reason = decision.reason_code.value if fresh else "stale_eligibility"
        eligible = decision.eligible and fresh
        record["eligibility"] = {
            "eligible": eligible, "reason_code": reason,
            "policy_reason_code": decision.reason_code.value,
            "evaluated_at": _stamp(now), "max_age_seconds": self.max_age,
            "mo2": {**asdict(mo2), "state": mo2.state.value,
                    "age_seconds": mo2_age},
            "endpoint_health": {**asdict(health), "state": health.state.value,
                                "observed_models": list(health.observed_models),
                                "age_seconds": health_age},
        }
        if not eligible:
            return None
        return RoleBinding(primary.role, primary.provider, OPTIONAL_NODE_ID,
                           OPTIONAL_ENDPOINT_ID, remote_endpoint.base_url, primary.model)

    def _infer(self, binding: RoleBinding, prompt: str) -> tuple[int, str, str | None]:
        body = {"model": binding.model,
                "messages": [{"role": "system", "content": "/no_think\nRespond concisely."},
                             {"role": "user", "content": prompt}],
                "temperature": 0, "max_tokens": 256,
                "chat_template_kwargs": {"enable_thinking": False}}
        request = urllib.request.Request(binding.endpoint.rstrip("/") + "/chat/completions",
                                         data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"},
                                         method="POST")
        try:
            status, raw = self.inference_transport(request, self.timeout)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            raise RuntimeError(f"HTTP error {status}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"inference transport failure: {exc}") from exc
        if status != 200:
            raise RuntimeError(f"unexpected HTTP status {status}")
        try:
            payload = json.loads(raw.decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            model = payload.get("model")
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"invalid response envelope: {exc}") from exc
        if not isinstance(content, str):
            raise RuntimeError("assistant content is not a string")
        response_model = model if isinstance(model, str) else None
        if response_model != binding.model:
            raise RuntimeError(
                f"server model identity mismatch: expected {binding.model}, got {response_model}")
        return status, content, response_model

    def _persist(self, record: dict[str, Any]) -> None:
        self.run_directory.mkdir(parents=True, exist_ok=True)
        destination = self.run_directory / f"{record['run_id']}.json"
        temporary = self.run_directory / f".{record['run_id']}.tmp"
        temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
