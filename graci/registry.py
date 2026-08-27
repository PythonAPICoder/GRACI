"""Deterministic Phase 3A resource, endpoint, and model registry."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping


REGISTRY_SCHEMA_VERSION = 1
PRIMARY_NODE_ID = "3090"
OPTIONAL_NODE_ID = "4090"
PRIMARY_ENDPOINT_ID = "3090-llama-cpp"
OPTIONAL_ENDPOINT_ID = "4090-llama-cpp"
QWEN_MODEL_ID = "qwen3.8-27b-q4_k_m"
GLM_MODEL_ID = "GLM-4.7-Flash-64x2.6B-Q4_K_M"
PRIMARY_BASE_URL = "http://127.0.0.1:8080/v1"
OPTIONAL_BASE_URL = "http://192.168.0.101:8080/v1"
LOCAL_PROVIDER_ID = "local-llama-cpp"


class NodeRole(str, Enum):
    PRIMARY = "primary"
    OPTIONAL = "optional"


class EndpointType(str, Enum):
    LLAMA_CPP_OPENAI = "llama-cpp-openai-compatible"


class HealthState(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class ModelRole(str, Enum):
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    VERIFIER = "verifier"
    GENERAL_REASONING = "general_reasoning"


class EligibilityReason(str, Enum):
    ELIGIBLE = "eligible"
    UNKNOWN_NODE = "unknown_node"
    UNKNOWN_ENDPOINT = "unknown_endpoint"
    UNKNOWN_MODEL = "unknown_model"
    MALFORMED_REFERENCE = "malformed_registry_reference"
    DISABLED_RESOURCE = "disabled_resource"
    UNKNOWN_HEALTH = "unknown_health"
    UNHEALTHY_ENDPOINT = "unhealthy_endpoint"
    MODEL_UNAVAILABLE = "model_unavailable"
    POLICY_BLOCKED_NODE = "policy_blocked_node"
    UNKNOWN_ROLE = "unknown_role"
    UNKNOWN_POLICY_STATE = "unknown_policy_state"


@dataclass(frozen=True)
class Node:
    node_id: str
    display_name: str
    role: NodeRole
    required: bool
    enabled: bool


@dataclass(frozen=True)
class Endpoint:
    endpoint_id: str
    node_id: str
    base_url: str
    endpoint_type: EndpointType
    enabled: bool = True
    health_state: HealthState = HealthState.UNKNOWN
    health_reason: str = "not_checked"
    last_checked_at: str | None = None
    observed_models: tuple[str, ...] = ()


@dataclass(frozen=True)
class Model:
    model_id: str
    provider_type: EndpointType
    endpoint_ids: tuple[str, ...]
    roles: frozenset[ModelRole]
    enabled: bool = True


@dataclass(frozen=True)
class Registry:
    schema_version: int
    nodes: Mapping[str, Node]
    endpoints: Mapping[str, Endpoint]
    models: Mapping[str, Model]

    def with_endpoint(self, endpoint: Endpoint) -> "Registry":
        updated = dict(self.endpoints)
        updated[endpoint.endpoint_id] = endpoint
        return replace(self, endpoints=MappingProxyType(updated))


@dataclass(frozen=True)
class HealthResult:
    state: HealthState
    reason: str
    checked_at: str
    observed_models: tuple[str, ...]
    http_status: int | None


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reason_code: EligibilityReason
    explanation: str


def build_phase3a_registry() -> Registry:
    nodes = {
        PRIMARY_NODE_ID: Node(PRIMARY_NODE_ID, "RTX 3090 primary", NodeRole.PRIMARY, True, True),
        OPTIONAL_NODE_ID: Node(OPTIONAL_NODE_ID, "RTX 4090 optional", NodeRole.OPTIONAL, False, True),
    }
    endpoints = {
        PRIMARY_ENDPOINT_ID: Endpoint(PRIMARY_ENDPOINT_ID, PRIMARY_NODE_ID,
                                      PRIMARY_BASE_URL,
                                      EndpointType.LLAMA_CPP_OPENAI),
        OPTIONAL_ENDPOINT_ID: Endpoint(OPTIONAL_ENDPOINT_ID, OPTIONAL_NODE_ID,
                                       OPTIONAL_BASE_URL,
                                       EndpointType.LLAMA_CPP_OPENAI),
    }
    models = {
        QWEN_MODEL_ID: Model(QWEN_MODEL_ID, EndpointType.LLAMA_CPP_OPENAI,
                            (PRIMARY_ENDPOINT_ID, OPTIONAL_ENDPOINT_ID),
                            frozenset({ModelRole.IMPLEMENTER, ModelRole.GENERAL_REASONING})),
        GLM_MODEL_ID: Model(GLM_MODEL_ID, EndpointType.LLAMA_CPP_OPENAI,
                           (PRIMARY_ENDPOINT_ID, OPTIONAL_ENDPOINT_ID),
                           frozenset({ModelRole.REVIEWER, ModelRole.VERIFIER})),
    }
    return Registry(REGISTRY_SCHEMA_VERSION, MappingProxyType(nodes),
                    MappingProxyType(endpoints), MappingProxyType(models))


HealthTransport = Callable[[urllib.request.Request, float], tuple[int, bytes]]


def _health_transport(request: urllib.request.Request, timeout: float) -> tuple[int, bytes]:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def check_openai_models_endpoint(endpoint: Endpoint, *, timeout_seconds: float = 3.0,
                                 expected_models: tuple[str, ...] = (),
                                 transport: HealthTransport = _health_transport) -> HealthResult:
    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if timeout_seconds <= 0:
        return HealthResult(HealthState.UNHEALTHY, "invalid_timeout", checked_at, (), None)
    request = urllib.request.Request(endpoint.base_url.rstrip("/") + "/models", method="GET")
    try:
        status, raw = transport(request, timeout_seconds)
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        return HealthResult(HealthState.UNHEALTHY, f"http_error:{status}", checked_at, (), status)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return HealthResult(HealthState.UNHEALTHY,
                            f"request_failure:{type(exc).__name__}", checked_at, (), None)
    if status != 200:
        return HealthResult(HealthState.UNHEALTHY, f"unexpected_http_status:{status}",
                            checked_at, (), status)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HealthResult(HealthState.UNHEALTHY, "malformed_json", checked_at, (), status)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return HealthResult(HealthState.UNHEALTHY, "missing_model_list", checked_at, (), status)
    model_ids: list[str] = []
    for item in payload["data"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            return HealthResult(HealthState.UNHEALTHY, "malformed_model_entry", checked_at, (), status)
        model_ids.append(item["id"])
    observed = tuple(sorted(set(model_ids)))
    missing = sorted(set(expected_models) - set(observed))
    if missing:
        return HealthResult(HealthState.UNHEALTHY, "expected_models_absent:" + ",".join(missing),
                            checked_at, observed, status)
    return HealthResult(HealthState.HEALTHY, "models_endpoint_valid", checked_at, observed, status)


def apply_health_result(endpoint: Endpoint, result: HealthResult) -> Endpoint:
    return replace(endpoint, health_state=result.state, health_reason=result.reason,
                   last_checked_at=result.checked_at, observed_models=result.observed_models)


def evaluate_eligibility(registry: Registry, node_id: str, endpoint_id: str, model_id: str,
                         *, required_role: ModelRole | str | None = None,
                         policy_state: str = "phase3a") -> EligibilityResult:
    if policy_state != "phase3a":
        return EligibilityResult(False, EligibilityReason.UNKNOWN_POLICY_STATE,
                                 "Only the Phase 3A policy state is recognized.")
    node = registry.nodes.get(node_id)
    if node is None:
        return EligibilityResult(False, EligibilityReason.UNKNOWN_NODE, "Node is not registered.")
    endpoint = registry.endpoints.get(endpoint_id)
    if endpoint is None:
        return EligibilityResult(False, EligibilityReason.UNKNOWN_ENDPOINT,
                                 "Endpoint is not registered.")
    model = registry.models.get(model_id)
    if model is None:
        return EligibilityResult(False, EligibilityReason.UNKNOWN_MODEL, "Model is not registered.")
    if endpoint.node_id != node_id or endpoint_id not in model.endpoint_ids:
        return EligibilityResult(False, EligibilityReason.MALFORMED_REFERENCE,
                                 "Registry node, endpoint, and model references do not agree.")
    if node_id == OPTIONAL_NODE_ID:
        return EligibilityResult(False, EligibilityReason.POLICY_BLOCKED_NODE,
                                 "Phase 3A does not authorize remote optional-node routing.")
    if not node.enabled or not endpoint.enabled or not model.enabled:
        return EligibilityResult(False, EligibilityReason.DISABLED_RESOURCE,
                                 "A required registry resource is disabled.")
    if required_role is not None:
        try:
            role = required_role if isinstance(required_role, ModelRole) else ModelRole(required_role)
        except ValueError:
            return EligibilityResult(False, EligibilityReason.UNKNOWN_ROLE,
                                     "The requested model role is not recognized.")
        if role not in model.roles:
            return EligibilityResult(False, EligibilityReason.MODEL_UNAVAILABLE,
                                     "The model does not advertise the requested role.")
    if endpoint.health_state == HealthState.UNKNOWN:
        return EligibilityResult(False, EligibilityReason.UNKNOWN_HEALTH,
                                 "Endpoint health has not been established.")
    if endpoint.health_state != HealthState.HEALTHY:
        return EligibilityResult(False, EligibilityReason.UNHEALTHY_ENDPOINT,
                                 f"Endpoint is unhealthy: {endpoint.health_reason}")
    if model_id not in endpoint.observed_models:
        return EligibilityResult(False, EligibilityReason.MODEL_UNAVAILABLE,
                                 "The required model was not observed at the endpoint.")
    return EligibilityResult(True, EligibilityReason.ELIGIBLE,
                             "Enabled primary resource is healthy and reports the required model.")
