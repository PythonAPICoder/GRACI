"""Phase 3C read-only optional-node availability policy."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from .registry import (
    OPTIONAL_BASE_URL,
    OPTIONAL_ENDPOINT_ID,
    OPTIONAL_NODE_ID,
    HealthState,
    Registry,
)


MO2_PROCESS_NAME = "ModOrganizer.exe"
MO2_STATUS_URL = "http://192.168.0.101:8765/graci/v1/mo2"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Mo2State(str, Enum):
    RUNNING = "RUNNING"
    NOT_RUNNING = "NOT_RUNNING"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


class Phase3CEligibilityReason(str, Enum):
    NODE_DISABLED = "node_disabled"
    MO2_RUNNING = "mo2_running"
    MO2_STATE_UNKNOWN = "mo2_state_unknown"
    MO2_QUERY_ERROR = "mo2_query_error"
    ENDPOINT_UNKNOWN = "endpoint_unknown"
    ENDPOINT_UNHEALTHY = "endpoint_unhealthy"
    REQUIRED_MODEL_UNAVAILABLE = "required_model_unavailable"
    POLICY_BLOCKED = "policy_blocked"
    ELIGIBLE = "eligible"


@dataclass(frozen=True)
class Mo2StatusResult:
    state: Mo2State
    reason_code: str
    checked_at: str
    http_status: int | None
    mechanism: str = "graci-mo2-status-http-v1"


@dataclass(frozen=True)
class Phase3CEligibilityResult:
    eligible: bool
    reason_code: Phase3CEligibilityReason
    explanation: str


Mo2Transport = Callable[[urllib.request.Request, float], tuple[int, bytes]]


def _mo2_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read(4097)


def check_4090_mo2_status(*, timeout_seconds: float = 3.0,
                          transport: Mo2Transport = _mo2_transport) -> Mo2StatusResult:
    """Query only the fixed 4090 endpoint and fail closed on every uncertainty."""
    checked_at = _timestamp()
    if timeout_seconds <= 0:
        return Mo2StatusResult(Mo2State.ERROR, "invalid_timeout", checked_at, None)
    request = urllib.request.Request(MO2_STATUS_URL, method="GET",
                                     headers={"Accept": "application/json"})
    try:
        status, raw = transport(request, timeout_seconds)
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        reason = "authentication_failure" if status in {401, 403} else f"http_error:{status}"
        return Mo2StatusResult(Mo2State.ERROR, reason, checked_at, status)
    except TimeoutError:
        return Mo2StatusResult(Mo2State.ERROR, "query_timeout", checked_at, None)
    except (urllib.error.URLError, OSError) as exc:
        return Mo2StatusResult(Mo2State.ERROR, f"query_failure:{type(exc).__name__}",
                               checked_at, None)
    if status in {401, 403}:
        return Mo2StatusResult(Mo2State.ERROR, "authentication_failure", checked_at, status)
    if status != 200:
        return Mo2StatusResult(Mo2State.ERROR, f"unexpected_http_status:{status}",
                               checked_at, status)
    if len(raw) > 4096:
        return Mo2StatusResult(Mo2State.UNKNOWN, "response_too_large", checked_at, status)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return Mo2StatusResult(Mo2State.UNKNOWN, "malformed_response", checked_at, status)
    expected_keys = {"schema_version", "process_name", "state", "reason_code"}
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        return Mo2StatusResult(Mo2State.UNKNOWN, "malformed_response", checked_at, status)
    if payload["schema_version"] != 1 or payload["process_name"] != MO2_PROCESS_NAME:
        return Mo2StatusResult(Mo2State.UNKNOWN, "identity_mismatch", checked_at, status)
    state, reason = payload["state"], payload["reason_code"]
    if not isinstance(reason, str) or not reason or len(reason) > 128:
        return Mo2StatusResult(Mo2State.UNKNOWN, "malformed_response", checked_at, status)
    allowed = {
        ("RUNNING", "exact_process_found"): Mo2State.RUNNING,
        ("NOT_RUNNING", "exact_process_absent"): Mo2State.NOT_RUNNING,
        ("ERROR", "process_query_error"): Mo2State.ERROR,
        ("ERROR", "request_handling_error"): Mo2State.ERROR,
    }
    parsed = allowed.get((state, reason))
    if parsed is None:
        return Mo2StatusResult(Mo2State.UNKNOWN, "contradictory_response", checked_at, status)
    return Mo2StatusResult(parsed, reason, checked_at, status)


def evaluate_4090_eligibility(registry: Registry, model_id: str,
                              mo2_status: Mo2StatusResult, *,
                              applicable_policy_checks_pass: bool = True
                              ) -> Phase3CEligibilityResult:
    """Evaluate Phase 3C eligibility only; this function cannot dispatch work."""
    node = registry.nodes.get(OPTIONAL_NODE_ID)
    endpoint = registry.endpoints.get(OPTIONAL_ENDPOINT_ID)
    model = registry.models.get(model_id)
    if node is None or not node.enabled:
        return Phase3CEligibilityResult(False, Phase3CEligibilityReason.NODE_DISABLED,
                                        "The optional 4090 node is absent or disabled.")
    if mo2_status.state == Mo2State.RUNNING:
        return Phase3CEligibilityResult(False, Phase3CEligibilityReason.MO2_RUNNING,
                                        "ModOrganizer.exe is running on the 4090.")
    if mo2_status.state == Mo2State.UNKNOWN:
        return Phase3CEligibilityResult(False, Phase3CEligibilityReason.MO2_STATE_UNKNOWN,
                                        "ModOrganizer.exe state is not definitive.")
    if mo2_status.state == Mo2State.ERROR:
        return Phase3CEligibilityResult(False, Phase3CEligibilityReason.MO2_QUERY_ERROR,
                                        "The ModOrganizer.exe query failed.")
    if endpoint is None or endpoint.health_state == HealthState.UNKNOWN:
        return Phase3CEligibilityResult(False, Phase3CEligibilityReason.ENDPOINT_UNKNOWN,
                                        "The 4090 llama.cpp endpoint health is unknown.")
    if endpoint.health_state != HealthState.HEALTHY:
        return Phase3CEligibilityResult(False, Phase3CEligibilityReason.ENDPOINT_UNHEALTHY,
                                        f"The 4090 endpoint is unhealthy: {endpoint.health_reason}")
    if (model is None or not model.enabled or endpoint is None or not endpoint.enabled or
            endpoint.node_id != OPTIONAL_NODE_ID or
            OPTIONAL_ENDPOINT_ID not in model.endpoint_ids or
            model_id not in endpoint.observed_models):
        return Phase3CEligibilityResult(
            False, Phase3CEligibilityReason.REQUIRED_MODEL_UNAVAILABLE,
            "The required model is not enabled and observed at the 4090 endpoint.")
    if endpoint.base_url != OPTIONAL_BASE_URL or not applicable_policy_checks_pass:
        return Phase3CEligibilityResult(False, Phase3CEligibilityReason.POLICY_BLOCKED,
                                        "An applicable fixed Phase 3C policy check failed.")
    return Phase3CEligibilityResult(True, Phase3CEligibilityReason.ELIGIBLE,
                                    "MO2 is absent and the optional endpoint and model are available.")
