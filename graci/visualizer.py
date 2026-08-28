"""Immutable, observer-only Phase 5A visualizer state and event contracts.

This module projects trusted runtime facts.  It has no provider, tool, memory-store,
routing, filesystem, or network capability and therefore cannot become an authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .availability import Mo2State
from .registry import GLM_MODEL_ID, QWEN_MODEL_ID, HealthState, NodeRole


SNAPSHOT_SCHEMA_VERSION = 1
EVENT_SCHEMA_VERSION = 1
RECENT_EVENT_LIMIT = 100
TASK_SUMMARY_LIMIT = 240
EVENT_MESSAGE_LIMIT = 320
ERROR_SUMMARY_LIMIT = 240
DISPLAY_LABEL_LIMIT = 160
METADATA_ENTRY_LIMIT = 16
METADATA_KEY_LIMIT = 64
METADATA_VALUE_LIMIT = 160


class SystemState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PLANNING = "planning"
    RETRIEVING_MEMORY = "retrieving_memory"
    REASONING = "reasoning"
    EXECUTING_TOOL = "executing_tool"
    TESTING = "testing"
    REVIEWING = "reviewing"
    ADJUDICATING = "adjudicating"
    COMPLETED = "completed"
    WARNING = "warning"
    FAILED = "failed"
    SPEAKING = "speaking"


class ActivityState(str, Enum):
    INACTIVE = "inactive"
    WAITING = "waiting"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class WorkflowStatus(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"
    PENDING = "pending"
    ACTIVE = "active"
    PASSED = "passed"
    FAILED = "failed"
    REJECTED = "rejected"


class MemoryMode(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    OPTIONAL = "optional"
    REQUIRED = "required"


class OperationCategory(str, Enum):
    INSPECT = "inspect"
    READ = "read"
    CREATE = "create"
    EDIT = "edit"
    COMMAND = "command"
    TEST = "test"
    VERIFY = "verify"
    REPAIR = "repair"
    ROUTE = "route"
    MEMORY_SELECT = "memory_select"


class EventSeverity(str, Enum):
    INFO = "info"
    ACTIVITY = "activity"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class EventType(str, Enum):
    SYSTEM_READY = "system_ready"
    SYSTEM_IDLE = "system_idle"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    ROUTE_SELECTED = "route_selected"
    ROUTE_FALLBACK = "route_fallback"
    NODE_INELIGIBLE = "node_ineligible"
    MO2_RUNNING = "mo2_running"
    ENDPOINT_UNHEALTHY = "endpoint_unhealthy"
    QWEN_STARTED = "qwen_started"
    QWEN_COMPLETED = "qwen_completed"
    GLM_STARTED = "glm_started"
    GLM_COMPLETED = "glm_completed"
    MEMORY_REQUESTED = "memory_requested"
    MEMORY_SELECTED = "memory_selected"
    NO_APPLICABLE_MEMORY = "no_applicable_memory"
    MEMORY_CONFLICT = "memory_conflict"
    MEMORY_UNAVAILABLE = "memory_unavailable"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    TESTS_STARTED = "tests_started"
    TESTS_PASSED = "tests_passed"
    TESTS_FAILED = "tests_failed"
    REVIEW_STARTED = "review_started"
    REVIEW_COMPLETED = "review_completed"
    ADJUDICATION_COMPLETED = "adjudication_completed"


_SECRET_NAME = re.compile(r"(?:secret|token|password|passwd|api[_-]?key|private[_-]?key|credential)", re.I)


def _aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _bounded(value: str | None, limit: int, name: str, *, allow_none: bool = True) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError(f"{name} must not be empty")
    if len(cleaned) <= limit:
        return cleaned
    if limit == 1:
        return "…"
    return cleaned[:limit - 1].rstrip() + "…"


def _enum(value: Any, enum_type: type[Enum], name: str) -> None:
    if not isinstance(value, enum_type):
        raise ValueError(f"{name} must be a {enum_type.__name__}")


@dataclass(frozen=True)
class EventMetadata:
    """Bounded JSON-scalar metadata; keys that look like secret containers fail closed."""

    entries: tuple[tuple[str, str | int | float | bool | None], ...] = ()

    def __post_init__(self) -> None:
        if len(self.entries) > METADATA_ENTRY_LIMIT:
            raise ValueError("event metadata has too many entries")
        seen: set[str] = set()
        normalized = []
        for key, value in self.entries:
            key = _bounded(key, METADATA_KEY_LIMIT, "metadata key", allow_none=False)
            if _SECRET_NAME.search(key):
                raise ValueError("secret-looking metadata key is not display-safe")
            if key in seen:
                raise ValueError("duplicate metadata key")
            if type(value) not in {str, int, float, bool, type(None)}:
                raise ValueError("metadata values must be JSON scalars")
            if isinstance(value, str):
                value = _bounded(value, METADATA_VALUE_LIMIT, "metadata value", allow_none=False)
            seen.add(key)
            normalized.append((key, value))
        object.__setattr__(self, "entries", tuple(sorted(normalized)))


@dataclass(frozen=True)
class VisualizerEvent:
    event_id: str
    timestamp: datetime
    event_type: EventType
    severity: EventSeverity
    source: str
    message: str
    task_id: str | None = None
    metadata: EventMetadata = EventMetadata()
    schema_version: int = EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EVENT_SCHEMA_VERSION:
            raise ValueError("unsupported event schema version")
        object.__setattr__(self, "event_id", _bounded(self.event_id, 128, "event_id", allow_none=False))
        _aware(self.timestamp, "event timestamp")
        _enum(self.event_type, EventType, "event_type")
        _enum(self.severity, EventSeverity, "severity")
        object.__setattr__(self, "source", _bounded(self.source, 80, "source", allow_none=False))
        object.__setattr__(self, "message", _bounded(self.message, EVENT_MESSAGE_LIMIT, "message", allow_none=False))
        object.__setattr__(self, "task_id", _bounded(self.task_id, 128, "task_id"))


@dataclass(frozen=True)
class RecentEventBuffer:
    events: tuple[VisualizerEvent, ...] = ()
    capacity: int = RECENT_EVENT_LIMIT

    def __post_init__(self) -> None:
        if not isinstance(self.capacity, int) or not 1 <= self.capacity <= RECENT_EVENT_LIMIT:
            raise ValueError(f"event capacity must be 1..{RECENT_EVENT_LIMIT}")
        if len(self.events) > self.capacity:
            raise ValueError("event buffer exceeds capacity")
        ids = [event.event_id for event in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate event IDs are not allowed")
        if any(self.events[index].timestamp > self.events[index + 1].timestamp
               for index in range(len(self.events) - 1)):
            raise ValueError("events must be ordered by nondecreasing timestamp")

    def append(self, event: VisualizerEvent, *, observed_at: datetime) -> "RecentEventBuffer":
        _aware(observed_at, "observed_at")
        if event.timestamp > observed_at:
            raise ValueError("future event timestamps are rejected")
        if any(existing.event_id == event.event_id for existing in self.events):
            raise ValueError("duplicate event ID")
        if self.events and event.timestamp < self.events[-1].timestamp:
            raise ValueError("out-of-order event timestamp")
        return RecentEventBuffer((self.events + (event,))[-self.capacity:], self.capacity)


@dataclass(frozen=True)
class TaskView:
    task_id: str | None = None
    goal_id: str | None = None
    summary: str | None = None
    started_at: datetime | None = None
    phase: str | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    final_status: WorkflowStatus = WorkflowStatus.NOT_APPLICABLE
    failure_category: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _bounded(self.task_id, 128, "task_id"))
        object.__setattr__(self, "goal_id", _bounded(self.goal_id, 128, "goal_id"))
        object.__setattr__(self, "summary", _bounded(self.summary, TASK_SUMMARY_LIMIT, "task summary"))
        if self.started_at is not None:
            _aware(self.started_at, "task started_at")
        object.__setattr__(self, "phase", _bounded(self.phase, DISPLAY_LABEL_LIMIT, "task phase"))
        _enum(self.final_status, WorkflowStatus, "task final_status")
        object.__setattr__(self, "failure_category", _bounded(self.failure_category, 80, "failure category"))
        object.__setattr__(self, "failure_reason", _bounded(self.failure_reason, ERROR_SUMMARY_LIMIT, "failure reason"))
        if (self.progress_current is None) != (self.progress_total is None):
            raise ValueError("task progress must provide both current and total")
        if self.progress_current is not None and not (0 <= self.progress_current <= self.progress_total):
            raise ValueError("task progress is invalid")


@dataclass(frozen=True)
class ComputeNodeView:
    node_id: str
    role: NodeRole
    availability: ActivityState
    endpoint_health: HealthState
    eligible: bool | None
    mo2_state: Mo2State | None
    policy_reason: str | None
    assigned_model: str | None = None
    assigned_role: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _bounded(self.node_id, 40, "node_id", allow_none=False))
        _enum(self.role, NodeRole, "node role")
        _enum(self.availability, ActivityState, "node availability")
        _enum(self.endpoint_health, HealthState, "endpoint health")
        if self.mo2_state is not None:
            _enum(self.mo2_state, Mo2State, "mo2_state")
        object.__setattr__(self, "policy_reason", _bounded(self.policy_reason, ERROR_SUMMARY_LIMIT, "policy reason"))
        object.__setattr__(self, "assigned_model", _bounded(self.assigned_model, DISPLAY_LABEL_LIMIT, "assigned model"))
        object.__setattr__(self, "assigned_role", _bounded(self.assigned_role, 80, "assigned role"))
        if self.node_id == "3090" and self.role is not NodeRole.PRIMARY:
            raise ValueError("3090 must be represented as primary")
        if self.node_id == "4090" and self.role is not NodeRole.OPTIONAL:
            raise ValueError("4090 must be represented as optional")
        if self.node_id == "4090" and self.mo2_state is Mo2State.RUNNING and self.eligible is not False:
            raise ValueError("MO2 RUNNING requires the 4090 to be ineligible")


@dataclass(frozen=True)
class ComputeView:
    primary_3090: ComputeNodeView
    optional_4090: ComputeNodeView


@dataclass(frozen=True)
class AgentView:
    model_id: str
    role: str
    state: ActivityState
    assigned_node: str | None = None
    activity: SystemState | None = None
    review_status: WorkflowStatus = WorkflowStatus.NOT_APPLICABLE
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _bounded(self.model_id, DISPLAY_LABEL_LIMIT, "model_id", allow_none=False))
        object.__setattr__(self, "role", _bounded(self.role, 80, "agent role", allow_none=False))
        _enum(self.state, ActivityState, "agent state")
        object.__setattr__(self, "assigned_node", _bounded(self.assigned_node, 40, "assigned node"))
        if self.activity is not None:
            _enum(self.activity, SystemState, "agent activity")
        _enum(self.review_status, WorkflowStatus, "review status")
        for name in ("started_at", "completed_at"):
            value = getattr(self, name)
            if value is not None:
                _aware(value, name)


@dataclass(frozen=True)
class AgentsView:
    qwen: AgentView
    glm: AgentView


@dataclass(frozen=True)
class MemoryView:
    requested: bool = False
    mode: MemoryMode = MemoryMode.NOT_APPLICABLE
    relevance_keys: tuple[str, ...] = ()
    selection_status: str | None = None
    selected_memory_ids: tuple[str, ...] = ()
    supplied_memory_ids: tuple[str, ...] = ()
    record_count: int = 0
    context_characters: int = 0
    conflict_count: int = 0
    corruption_count: int = 0

    def __post_init__(self) -> None:
        _enum(self.mode, MemoryMode, "memory mode")
        if len(self.relevance_keys) > 50 or len(self.selected_memory_ids) > 100 or len(self.supplied_memory_ids) > 100:
            raise ValueError("memory metadata exceeds contract bounds")
        for value in self.relevance_keys:
            _bounded(value, 128, "relevance key", allow_none=False)
        for value in self.selected_memory_ids + self.supplied_memory_ids:
            _bounded(value, 128, "memory ID", allow_none=False)
        object.__setattr__(self, "selection_status", _bounded(self.selection_status, 80, "selection status"))
        if any(type(value) is not int or value < 0 for value in
               (self.record_count, self.context_characters, self.conflict_count, self.corruption_count)):
            raise ValueError("memory counts must be nonnegative integers")
        if not self.requested and (self.mode is not MemoryMode.NOT_APPLICABLE or self.record_count):
            raise ValueError("unrequested memory must be not_applicable and empty")


@dataclass(frozen=True)
class OperationView:
    category: OperationCategory
    status: WorkflowStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    target_label: str | None = None
    error_code: str | None = None
    error_reason: str | None = None

    def __post_init__(self) -> None:
        _enum(self.category, OperationCategory, "operation category")
        _enum(self.status, WorkflowStatus, "operation status")
        for name in ("started_at", "completed_at"):
            value = getattr(self, name)
            if value is not None:
                _aware(value, name)
        object.__setattr__(self, "target_label", _bounded(self.target_label, DISPLAY_LABEL_LIMIT, "target label"))
        object.__setattr__(self, "error_code", _bounded(self.error_code, 80, "error code"))
        object.__setattr__(self, "error_reason", _bounded(self.error_reason, ERROR_SUMMARY_LIMIT, "error reason"))


@dataclass(frozen=True)
class TestView:
    status: WorkflowStatus = WorkflowStatus.NOT_APPLICABLE
    command_label: str | None = None
    passed_count: int | None = None
    failed_count: int | None = None
    total_count: int | None = None
    duration_ms: int | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        _enum(self.status, WorkflowStatus, "test status")
        object.__setattr__(self, "command_label", _bounded(self.command_label, DISPLAY_LABEL_LIMIT, "test command label"))
        object.__setattr__(self, "failure_reason", _bounded(self.failure_reason, ERROR_SUMMARY_LIMIT, "test failure reason"))
        for name in ("passed_count", "failed_count", "total_count", "duration_ms"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer or null")
        if self.total_count is not None and self.passed_count is not None and self.failed_count is not None:
            if self.passed_count + self.failed_count != self.total_count:
                raise ValueError("test counts do not add to total")
        if self.failed_count and self.status is WorkflowStatus.PASSED:
            raise ValueError("failing deterministic tests cannot be represented as passed")


@dataclass(frozen=True)
class ReviewView:
    requested: bool = False
    reviewer_model_id: str | None = None
    reviewer_status: WorkflowStatus = WorkflowStatus.NOT_APPLICABLE
    structured_verdict: str | None = None
    finding_count: int = 0
    adjudication_status: WorkflowStatus = WorkflowStatus.NOT_APPLICABLE
    final_outcome: str | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reviewer_model_id", _bounded(self.reviewer_model_id, DISPLAY_LABEL_LIMIT, "reviewer model"))
        _enum(self.reviewer_status, WorkflowStatus, "reviewer status")
        _enum(self.adjudication_status, WorkflowStatus, "adjudication status")
        if self.structured_verdict not in {None, "PASS", "FAIL"}:
            raise ValueError("review verdict must be PASS, FAIL, or null")
        if type(self.finding_count) is not int or not 0 <= self.finding_count <= 10:
            raise ValueError("finding count must be 0..10")
        object.__setattr__(self, "final_outcome", _bounded(self.final_outcome, 80, "final outcome"))
        object.__setattr__(self, "reason_code", _bounded(self.reason_code, 128, "adjudication reason"))
        if not self.requested and self.reviewer_status is not WorkflowStatus.NOT_APPLICABLE:
            raise ValueError("inactive reviewer must be not_applicable")


@dataclass(frozen=True)
class ExecutionView:
    operations: tuple[OperationView, ...] = ()
    tests: TestView = TestView()

    def __post_init__(self) -> None:
        if len(self.operations) > 25:
            raise ValueError("too many recent operations")


@dataclass(frozen=True)
class VisualizerSnapshot:
    snapshot_id: str
    generated_at: datetime
    system_state: SystemState
    task: TaskView
    compute: ComputeView
    agents: AgentsView
    memory: MemoryView
    execution: ExecutionView
    review: ReviewView
    recent_events: tuple[VisualizerEvent, ...] = ()
    schema_version: int = SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported snapshot schema version")
        object.__setattr__(self, "snapshot_id", _bounded(self.snapshot_id, 128, "snapshot_id", allow_none=False))
        _aware(self.generated_at, "generated_at")
        _enum(self.system_state, SystemState, "system_state")
        RecentEventBuffer(self.recent_events)
        if any(event.timestamp > self.generated_at for event in self.recent_events):
            raise ValueError("snapshot cannot contain future events")


@dataclass(frozen=True)
class TrustedRuntimeState:
    """Typed input facts owned by the runtime/controller, never by a model response."""

    controller_state: SystemState
    task: TaskView
    compute: ComputeView
    agents: AgentsView
    memory: MemoryView
    execution: ExecutionView
    review: ReviewView
    deterministic_tests_failed: bool = False
    deterministic_terminal_status: str | None = None

    def __post_init__(self) -> None:
        _enum(self.controller_state, SystemState, "controller_state")
        if type(self.deterministic_tests_failed) is not bool:
            raise ValueError("deterministic_tests_failed must be boolean")
        if self.deterministic_terminal_status not in {None, "PASS", "COMPLETED", "FAIL"}:
            raise ValueError("deterministic_terminal_status is not recognized")


def derive_system_state(source: TrustedRuntimeState) -> SystemState:
    """Derive terminal truth from controller/test facts; model claims are absent by design."""
    if source.deterministic_tests_failed or source.deterministic_terminal_status == "FAIL":
        return SystemState.FAILED
    if source.controller_state is SystemState.COMPLETED:
        if source.deterministic_terminal_status not in {"PASS", "COMPLETED"}:
            return SystemState.WARNING
        return SystemState.COMPLETED
    if source.controller_state is SystemState.FAILED:
        return SystemState.FAILED
    return source.controller_state


def project_snapshot(source: TrustedRuntimeState, *, snapshot_id: str,
                     generated_at: datetime, events: RecentEventBuffer | None = None
                     ) -> VisualizerSnapshot:
    """Pure deterministic projection.  Source objects are read but never mutated."""
    return VisualizerSnapshot(
        snapshot_id=snapshot_id, generated_at=generated_at,
        system_state=derive_system_state(source), task=source.task,
        compute=source.compute, agents=source.agents, memory=source.memory,
        execution=source.execution, review=source.review,
        recent_events=() if events is None else events.events)


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        _aware(value, "serialized timestamp")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, EventMetadata):
        return {key: _json_value(item) for key, item in value.entries}
    if is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if type(value) in {str, int, float, bool, type(None)}:
        return value
    raise TypeError(f"unsupported visualizer serialization type: {type(value).__name__}")


def to_json_compatible(value: VisualizerSnapshot | VisualizerEvent) -> dict[str, Any]:
    return _json_value(value)


def serialize_visualizer(value: VisualizerSnapshot | VisualizerEvent) -> str:
    return json.dumps(to_json_compatible(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def default_compute(*, primary_health: HealthState = HealthState.UNKNOWN,
                    optional_health: HealthState = HealthState.UNKNOWN,
                    optional_eligible: bool | None = None,
                    mo2_state: Mo2State | None = None,
                    optional_reason: str | None = "not_checked") -> ComputeView:
    """Construct the fixed topology from already-observed facts; performs no probe."""
    primary_availability = (ActivityState.UNKNOWN if primary_health is HealthState.UNKNOWN
                            else ActivityState.ACTIVE if primary_health is HealthState.HEALTHY
                            else ActivityState.FAILED)
    optional_availability = (ActivityState.UNKNOWN if optional_health is HealthState.UNKNOWN
                             else ActivityState.ACTIVE if optional_health is HealthState.HEALTHY
                             else ActivityState.FAILED)
    if mo2_state is Mo2State.RUNNING:
        optional_availability = ActivityState.INACTIVE
        optional_eligible = False
        optional_reason = "mo2_running"
    return ComputeView(
        ComputeNodeView("3090", NodeRole.PRIMARY, primary_availability,
                        primary_health, True if primary_health is HealthState.HEALTHY else None,
                        None, None),
        ComputeNodeView("4090", NodeRole.OPTIONAL, optional_availability,
                        optional_health, optional_eligible, mo2_state, optional_reason))


def inactive_agents() -> AgentsView:
    return AgentsView(
        AgentView(QWEN_MODEL_ID, "implementer", ActivityState.INACTIVE),
        AgentView(GLM_MODEL_ID, "reviewer", ActivityState.INACTIVE))
