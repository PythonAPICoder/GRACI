"""Pure, bounded Phase 8D runtime-readiness and conversational-context contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


RUNTIME_CONTEXT_SCHEMA_VERSION = 1
MAX_COMPONENTS = 24
MAX_REASON = 240
MAX_FACTS = 12
MAX_FACT_KEY = 64
MAX_FACT_VALUE = 160
DEFAULT_FRESH_SECONDS = 30


class ReadinessState(str, Enum):
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


class ComponentState(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class StartupStage(str, Enum):
    MISSING = "missing"
    ACCESS_DENIED_UNKNOWN = "access_denied_unknown"
    REGISTERED = "registered"
    LAUNCHER_SUCCEEDED = "launcher_succeeded"
    PROCESS_ALIVE = "process_alive"
    RUNTIME_READY = "runtime_ready"


_ALLOWED_COMPONENTS = frozenset({
    "trusted_clock",
    "resident_scheduled_task", "router_scheduled_task",
    "resident_process", "resident_runtime",
    "router_endpoint", "qwen_model", "glm_model",
    "optional_4090_endpoint", "optional_4090_mo2", "optional_4090_eligibility",
    "stt_resources", "tts_resources",
})


def _aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _bounded(value: str, limit: int, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = " ".join(value.split())
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"


@dataclass(frozen=True)
class ComponentReadiness:
    component_id: str
    required: bool
    state: ComponentState
    observed_at: datetime
    reason: str
    startup_stage: StartupStage | None = None
    facts: tuple[tuple[str, str | int | float | bool | None], ...] = ()

    def __post_init__(self) -> None:
        if self.component_id not in _ALLOWED_COMPONENTS:
            raise ValueError("component_id is not in the Phase 8D allowlist")
        if type(self.required) is not bool:
            raise ValueError("required must be boolean")
        if not isinstance(self.state, ComponentState):
            raise ValueError("state must be a ComponentState")
        _aware(self.observed_at, "component observed_at")
        object.__setattr__(self, "reason", _bounded(self.reason, MAX_REASON, "reason"))
        if self.startup_stage is not None and not isinstance(self.startup_stage, StartupStage):
            raise ValueError("startup_stage must be a StartupStage")
        if len(self.facts) > MAX_FACTS:
            raise ValueError("component facts exceed the bounded limit")
        seen: set[str] = set()
        normalized = []
        for key, value in self.facts:
            key = _bounded(key, MAX_FACT_KEY, "fact key")
            if key in seen or any(marker in key.lower() for marker in
                                  ("secret", "token", "password", "credential", "api_key")):
                raise ValueError("component fact key is duplicated or unsafe")
            if type(value) not in {str, int, float, bool, type(None)}:
                raise ValueError("component facts must be JSON scalars")
            if isinstance(value, str):
                value = _bounded(value, MAX_FACT_VALUE, "fact value")
            seen.add(key)
            normalized.append((key, value))
        object.__setattr__(self, "facts", tuple(sorted(normalized)))


@dataclass(frozen=True)
class RuntimeReadiness:
    observed_at: datetime
    fresh_until: datetime
    state: ReadinessState
    local_datetime: str
    timezone_name: str
    utc_offset: str
    components: tuple[ComponentReadiness, ...]
    previous_state: ReadinessState | None = None
    schema_version: int = RUNTIME_CONTEXT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RUNTIME_CONTEXT_SCHEMA_VERSION:
            raise ValueError("unsupported runtime context schema version")
        _aware(self.observed_at, "runtime observed_at")
        _aware(self.fresh_until, "runtime fresh_until")
        if self.fresh_until <= self.observed_at:
            raise ValueError("fresh_until must follow observed_at")
        if not isinstance(self.state, ReadinessState):
            raise ValueError("state must be a ReadinessState")
        if self.previous_state is not None and not isinstance(self.previous_state, ReadinessState):
            raise ValueError("previous_state must be a ReadinessState")
        object.__setattr__(self, "local_datetime", _bounded(
            self.local_datetime, 64, "local_datetime"))
        object.__setattr__(self, "timezone_name", _bounded(
            self.timezone_name, 80, "timezone_name"))
        object.__setattr__(self, "utc_offset", _bounded(
            self.utc_offset, 12, "utc_offset"))
        if not 1 <= len(self.components) <= MAX_COMPONENTS:
            raise ValueError("runtime context component count is invalid")
        ids = [item.component_id for item in self.components]
        if len(ids) != len(set(ids)):
            raise ValueError("runtime context contains duplicate components")

    def prompt_context(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Return only allowlisted read-only facts; these facts never grant authority."""
        checked = now or datetime.now(timezone.utc)
        _aware(checked, "context current time")
        fresh = checked <= self.fresh_until
        state = self.state if fresh else ReadinessState.DEGRADED
        return {
            "schema_version": self.schema_version,
            "authority": "read_only_runtime_facts_no_new_authority",
            "observed_at": _iso(self.observed_at),
            "fresh_until": _iso(self.fresh_until),
            "fresh": fresh,
            "state": state.value,
            "local_datetime": self.local_datetime,
            "timezone_name": self.timezone_name,
            "utc_offset": self.utc_offset,
            "components": [
                {
                    "id": item.component_id,
                    "required": item.required,
                    "state": item.state.value,
                    "reason": item.reason,
                    "startup_stage": (item.startup_stage.value
                                      if item.startup_stage is not None else None),
                    "facts": dict(item.facts),
                }
                for item in self.components
            ],
        }


def reduce_readiness(components: tuple[ComponentReadiness, ...], *,
                     observed_at: datetime, local_now: datetime,
                     previous_state: ReadinessState | None = None,
                     fresh_seconds: int = DEFAULT_FRESH_SECONDS) -> RuntimeReadiness:
    """Deterministically reduce observations without creating runtime authority."""
    _aware(observed_at, "observed_at")
    _aware(local_now, "local_now")
    if not 5 <= fresh_seconds <= 300:
        raise ValueError("fresh_seconds must be between 5 and 300")
    required = tuple(item for item in components if item.required)
    if any(item.state is ComponentState.UNAVAILABLE for item in required):
        state = ReadinessState.UNAVAILABLE
    elif any(item.state in {ComponentState.DEGRADED, ComponentState.BLOCKED,
                            ComponentState.UNKNOWN} for item in required):
        state = ReadinessState.DEGRADED
    else:
        state = ReadinessState.READY
    if (state is ReadinessState.READY and
            previous_state in {ReadinessState.DEGRADED, ReadinessState.UNAVAILABLE}):
        state = ReadinessState.RECOVERING
    offset = local_now.strftime("%z")
    offset = f"{offset[:3]}:{offset[3:]}" if len(offset) == 5 else offset
    return RuntimeReadiness(
        observed_at=observed_at,
        fresh_until=observed_at + timedelta(seconds=fresh_seconds),
        state=state,
        previous_state=previous_state,
        local_datetime=local_now.isoformat(timespec="seconds"),
        timezone_name=str(local_now.tzname() or "unknown"),
        utc_offset=offset or "+00:00",
        components=components,
    )


def validate_prompt_context(value: object) -> dict[str, Any]:
    """Validate the serialized trust boundary before it reaches a provider."""
    if not isinstance(value, dict) or set(value) != {
            "schema_version", "authority", "observed_at", "fresh_until", "fresh",
            "state", "local_datetime", "timezone_name", "utc_offset", "components"}:
        raise ValueError("trusted runtime context has an invalid top-level shape")
    if (value["schema_version"] != RUNTIME_CONTEXT_SCHEMA_VERSION or
            value["authority"] != "read_only_runtime_facts_no_new_authority" or
            type(value["fresh"]) is not bool or
            value["state"] not in {item.value for item in ReadinessState}):
        raise ValueError("trusted runtime context identity is invalid")
    for key, limit in (("observed_at", 64), ("fresh_until", 64),
                       ("local_datetime", 64), ("timezone_name", 80),
                       ("utc_offset", 12)):
        if not isinstance(value[key], str) or not value[key] or len(value[key]) > limit:
            raise ValueError(f"trusted runtime context {key} is invalid")
    components = value["components"]
    if not isinstance(components, list) or not 1 <= len(components) <= MAX_COMPONENTS:
        raise ValueError("trusted runtime context components are invalid")
    seen: set[str] = set()
    for item in components:
        if not isinstance(item, dict) or set(item) != {
                "id", "required", "state", "reason", "startup_stage", "facts"}:
            raise ValueError("trusted runtime component shape is invalid")
        component_id = item["id"]
        if component_id not in _ALLOWED_COMPONENTS or component_id in seen:
            raise ValueError("trusted runtime component identity is invalid")
        if (type(item["required"]) is not bool or
                item["state"] not in {state.value for state in ComponentState} or
                not isinstance(item["reason"], str) or
                not 1 <= len(item["reason"]) <= MAX_REASON):
            raise ValueError("trusted runtime component values are invalid")
        stage = item["startup_stage"]
        if stage is not None and stage not in {candidate.value for candidate in StartupStage}:
            raise ValueError("trusted runtime startup stage is invalid")
        facts = item["facts"]
        if not isinstance(facts, dict) or len(facts) > MAX_FACTS:
            raise ValueError("trusted runtime component facts are invalid")
        for key, fact in facts.items():
            if (not isinstance(key, str) or not 1 <= len(key) <= MAX_FACT_KEY or
                    any(marker in key.lower() for marker in
                        ("secret", "token", "password", "credential", "api_key")) or
                    type(fact) not in {str, int, float, bool, type(None)} or
                    (isinstance(fact, str) and len(fact) > MAX_FACT_VALUE)):
                raise ValueError("trusted runtime component fact is invalid")
        seen.add(component_id)
    return value


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
