"""Stateful Phase 5D projection of trusted runtime observations."""

from __future__ import annotations

import threading
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .availability import Mo2State
from .observation import ObservationKind, RuntimeObservation
from .registry import GLM_MODEL_ID, QWEN_MODEL_ID, HealthState, NodeRole
from .visualizer import (
    ActivityState, AgentView, AgentsView, ComputeNodeView, ComputeView,
    EventMetadata, EventSeverity, EventType, ExecutionView, MemoryMode,
    MemoryView, OperationCategory, OperationView, RecentEventBuffer, ReviewView,
    SystemState, TaskView, TestView, TrustedRuntimeState, VisualizerEvent,
    WorkflowStatus, default_compute, inactive_agents, project_snapshot,
)
from .visualizer_backend import VisualizerStateProvider
from .voice_lifecycle import VoiceLifecycleEvent


_EVENT_TYPES = {
    ObservationKind.TASK_STARTED: EventType.TASK_STARTED,
    ObservationKind.MEMORY_STARTED: EventType.MEMORY_REQUESTED,
    ObservationKind.MEMORY_COMPLETED: EventType.MEMORY_SELECTED,
    ObservationKind.MODEL_STARTED: EventType.QWEN_STARTED,
    ObservationKind.MODEL_COMPLETED: EventType.QWEN_COMPLETED,
    ObservationKind.TOOL_STARTED: EventType.TOOL_STARTED,
    ObservationKind.TOOL_COMPLETED: EventType.TOOL_COMPLETED,
    ObservationKind.TESTS_STARTED: EventType.TESTS_STARTED,
    ObservationKind.TESTS_COMPLETED: EventType.TESTS_PASSED,
    ObservationKind.REVIEW_STARTED: EventType.REVIEW_STARTED,
    ObservationKind.REVIEW_COMPLETED: EventType.REVIEW_COMPLETED,
    ObservationKind.ADJUDICATION_COMPLETED: EventType.ADJUDICATION_COMPLETED,
    ObservationKind.ROUTE_COMPLETED: EventType.ROUTE_SELECTED,
    ObservationKind.TASK_COMPLETED: EventType.TASK_COMPLETED,
    ObservationKind.TASK_FAILED: EventType.TASK_FAILED,
}


class VisualizerRuntimeObserver:
    """In-process projector/publication adapter; exposes no control methods."""

    def __init__(self, provider: VisualizerStateProvider):
        self.provider = provider
        self.events = RecentEventBuffer()
        self.state = SystemState.IDLE
        self.task = TaskView()
        self.compute = default_compute()
        self.agents = inactive_agents()
        self.memory = MemoryView()
        self.execution = ExecutionView()
        self.review = ReviewView()
        self.terminal: str | None = None
        self.tests_failed = False
        self._lock = threading.RLock()

    def observe(self, observation: RuntimeObservation) -> None:
        with self._lock:
            facts = dict(observation.facts)
            self._apply(observation, facts)
            event = self._event(observation, facts)
            if event is not None:
                self._publish_event(event)
            self._publish_snapshot(observation.run_id)

    def publish_current(self, source_id: str = "resident") -> None:
        """Publish current trusted state without manufacturing a runtime event."""
        with self._lock:
            self._publish_snapshot(source_id)

    def reset_transient(self) -> None:
        """Clear runtime projection only; durable run records remain untouched."""
        with self._lock:
            self.state = SystemState.IDLE
            self.task = TaskView()
            self.compute = default_compute()
            self.agents = inactive_agents()
            self.memory = MemoryView()
            self.execution = ExecutionView()
            self.review = ReviewView()
            self.terminal = None
            self.tests_failed = False
            self._publish_snapshot("resident-restart")

    def publish_voice(self, event: VoiceLifecycleEvent) -> None:
        """Project bounded presentation activity without changing runtime authority."""
        with self._lock:
            if event.state is SystemState.LISTENING:
                event_type = EventType.VOICE_LISTENING
            elif event.state is SystemState.SPEAKING:
                event_type = EventType.VOICE_SPEAKING
            elif event.state is SystemState.IDLE:
                event_type = EventType.SYSTEM_IDLE
            else:
                raise ValueError("unsupported voice lifecycle state")
            display_state = event.state
            if event.state is SystemState.IDLE and self.terminal is not None:
                display_state = (SystemState.COMPLETED if self.terminal == "PASS"
                                 else SystemState.FAILED)
            self.state = display_state
            projected = VisualizerEvent(
                uuid.uuid4().hex, event.timestamp, event_type, EventSeverity.ACTIVITY,
                "voice", f"voice {event.state.value}", self.task.task_id,
                EventMetadata((("sequence", event.sequence),)),
            )
            self._publish_event(projected)
            self._publish_snapshot(self.task.task_id or "voice")

    def _publish_event(self, event: VisualizerEvent) -> None:
        observed_at = datetime.now(timezone.utc)
        self.events = self.events.append(event, observed_at=observed_at)
        self.provider.publish_event(event, observed_at=observed_at)

    def _publish_snapshot(self, source_id: str) -> None:
        source = TrustedRuntimeState(
            self.state, self.task, self.compute, self.agents, self.memory,
            self.execution, self.review, self.tests_failed, self.terminal)
        snapshot = project_snapshot(source, snapshot_id=f"{source_id}:{uuid.uuid4().hex}",
                                    generated_at=datetime.now(timezone.utc), events=self.events)
        self.provider.publish_snapshot(snapshot)

    def _apply(self, item: RuntimeObservation, facts: dict[str, Any]) -> None:
        kind, at = item.kind, item.timestamp
        if kind is ObservationKind.TASK_STARTED:
            self.state = SystemState.PLANNING
            self.task = TaskView(item.run_id, summary=facts.get("summary"), started_at=at,
                                 phase="planning", final_status=WorkflowStatus.ACTIVE)
        elif kind is ObservationKind.PLANNING_STARTED:
            self._phase(SystemState.PLANNING)
        elif kind is ObservationKind.MEMORY_STARTED:
            self._phase(SystemState.RETRIEVING_MEMORY)
        elif kind is ObservationKind.MEMORY_COMPLETED:
            requested = bool(facts.get("requested"))
            mode = MemoryMode(facts["mode"]) if requested else MemoryMode.NOT_APPLICABLE
            self.memory = MemoryView(
                requested, mode, tuple(facts.get("relevance_keys", ())), facts.get("status"),
                tuple(facts.get("selected_ids", ())), tuple(facts.get("supplied_ids", ())),
                int(facts.get("supplied_count", 0)), int(facts.get("context_characters", 0)),
                int(facts.get("conflict_count", 0)), int(facts.get("corruption_count", 0)))
        elif kind is ObservationKind.MODEL_STARTED:
            self._phase(SystemState.REASONING)
            role, model, node = facts.get("role"), facts.get("model"), facts.get("node")
            active = AgentView(model, role, ActivityState.ACTIVE, node,
                               SystemState.REASONING, started_at=at)
            self.agents = (AgentsView(active, self.agents.glm) if role == "implementer"
                           else AgentsView(self.agents.qwen, active))
            self._assign_compute(node, model, role, ActivityState.ACTIVE)
        elif kind is ObservationKind.MODEL_COMPLETED:
            role = facts.get("role")
            agent = self.agents.qwen if role == "implementer" else self.agents.glm
            done = replace(agent, state=ActivityState.COMPLETED, completed_at=at)
            self.agents = (AgentsView(done, self.agents.glm) if role == "implementer"
                           else AgentsView(self.agents.qwen, done))
        elif kind is ObservationKind.TOOL_STARTED:
            self._phase(SystemState.EXECUTING_TOOL)
            self._operation(facts, WorkflowStatus.ACTIVE, at)
        elif kind is ObservationKind.TOOL_COMPLETED:
            self._complete_operation(facts, at)
        elif kind is ObservationKind.TESTS_STARTED:
            self._phase(SystemState.TESTING)
            self.execution = replace(self.execution, tests=TestView(
                WorkflowStatus.ACTIVE, "warning-strict deterministic tests"))
        elif kind is ObservationKind.TESTS_COMPLETED:
            passed = bool(facts.get("passed")); self.tests_failed = not passed
            status = WorkflowStatus.PASSED if passed else WorkflowStatus.FAILED
            self.execution = replace(self.execution, tests=TestView(
                status, "warning-strict deterministic tests",
                facts.get("passed_count"), facts.get("failed_count"), facts.get("total_count"),
                facts.get("duration_ms"), None if passed else facts.get("reason")))
        elif kind is ObservationKind.REVIEW_STARTED:
            self._phase(SystemState.REVIEWING)
            self.review = ReviewView(True, facts.get("model"), WorkflowStatus.ACTIVE)
            self.agents = AgentsView(self.agents.qwen, AgentView(
                facts.get("model", GLM_MODEL_ID), "reviewer", ActivityState.ACTIVE,
                facts.get("node"), SystemState.REVIEWING, WorkflowStatus.ACTIVE, at))
        elif kind is ObservationKind.REVIEW_COMPLETED:
            passed = facts.get("status") == "COMPLETE"
            status = WorkflowStatus.PASSED if passed else WorkflowStatus.FAILED
            self.review = replace(self.review, reviewer_status=status,
                                  structured_verdict=facts.get("verdict"),
                                  finding_count=int(facts.get("finding_count", 0)))
        elif kind is ObservationKind.ADJUDICATION_STARTED:
            self._phase(SystemState.ADJUDICATING)
        elif kind is ObservationKind.ADJUDICATION_COMPLETED:
            passed = facts.get("result") == "PASS"
            self.review = replace(self.review,
                adjudication_status=WorkflowStatus.PASSED if passed else WorkflowStatus.REJECTED,
                final_outcome=facts.get("result"), reason_code=facts.get("reason"))
        elif kind is ObservationKind.ROUTE_COMPLETED:
            self._apply_route(facts)
        elif kind is ObservationKind.TASK_COMPLETED:
            self.state, self.terminal = SystemState.COMPLETED, "PASS"
            self.task = replace(self.task, phase="completed", final_status=WorkflowStatus.PASSED)
        elif kind is ObservationKind.TASK_WARNING:
            self.state = SystemState.WARNING
        elif kind is ObservationKind.TASK_FAILED:
            self.state, self.terminal = SystemState.FAILED, "FAIL"
            self.task = replace(self.task, phase="failed", final_status=WorkflowStatus.FAILED,
                                failure_category=facts.get("category"),
                                failure_reason=facts.get("reason"))

    def _phase(self, state: SystemState) -> None:
        self.state = state
        if self.task.task_id:
            self.task = replace(self.task, phase=state.value)

    def _operation(self, facts: dict[str, Any], status: WorkflowStatus, at: datetime) -> None:
        category = OperationCategory(facts.get("category", "inspect"))
        operations = (*self.execution.operations, OperationView(
            category, status, started_at=at, target_label=facts.get("target")))
        self.execution = replace(self.execution, operations=operations[-25:])

    def _complete_operation(self, facts: dict[str, Any], at: datetime) -> None:
        if not self.execution.operations:
            return
        passed = bool(facts.get("success"))
        status = WorkflowStatus.PASSED if passed else WorkflowStatus.FAILED
        last = replace(self.execution.operations[-1], status=status, completed_at=at,
                       error_code=None if passed else facts.get("error_code"),
                       error_reason=None if passed else facts.get("reason"))
        self.execution = replace(self.execution,
                                 operations=(*self.execution.operations[:-1], last))

    def _assign_compute(self, node: str, model: str, role: str,
                        state: ActivityState) -> None:
        primary = isinstance(node, str) and node.startswith("3090")
        target = self.compute.primary_3090 if primary else self.compute.optional_4090
        target = replace(target, availability=state, assigned_model=model, assigned_role=role)
        self.compute = (replace(self.compute, primary_3090=target) if primary
                        else replace(self.compute, optional_4090=target))

    def _apply_route(self, facts: dict[str, Any]) -> None:
        eligibility = facts.get("eligibility") or {}
        mo2 = (eligibility.get("mo2") or {}).get("state")
        health = (eligibility.get("endpoint_health") or {}).get("state")
        availability = (ActivityState.INACTIVE if mo2 == Mo2State.RUNNING.value
                        else self.compute.optional_4090.availability)
        optional = replace(self.compute.optional_4090,
            availability=availability,
            eligible=eligibility.get("eligible"),
            mo2_state=Mo2State(mo2) if mo2 else None,
            endpoint_health=HealthState(health) if health else HealthState.UNKNOWN,
            policy_reason=eligibility.get("reason_code"))
        self.compute = replace(self.compute, optional_4090=optional)
        node, model, role = facts.get("node"), facts.get("model"), facts.get("role")
        if node in {"3090", "4090"} and model and role:
            self._assign_compute(node, model, role, ActivityState.COMPLETED)
            completed = AgentView(model, role, ActivityState.COMPLETED, node,
                                  SystemState.REASONING, completed_at=datetime.now(timezone.utc))
            self.agents = (AgentsView(completed, self.agents.glm) if role == "implementer"
                           else AgentsView(self.agents.qwen, completed))

    def _event(self, item: RuntimeObservation, facts: dict[str, Any]) -> VisualizerEvent | None:
        event_type = _EVENT_TYPES.get(item.kind)
        if item.kind is ObservationKind.MODEL_STARTED and facts.get("role") == "reviewer":
            event_type = EventType.GLM_STARTED
        elif item.kind is ObservationKind.MODEL_COMPLETED and facts.get("role") == "reviewer":
            event_type = EventType.GLM_COMPLETED
        elif item.kind is ObservationKind.TESTS_COMPLETED:
            event_type = EventType.TESTS_PASSED if facts.get("passed") else EventType.TESTS_FAILED
        elif item.kind is ObservationKind.TOOL_COMPLETED and not facts.get("success"):
            event_type = EventType.TOOL_FAILED
        elif item.kind is ObservationKind.ROUTE_COMPLETED and not facts.get("success", True):
            event_type = (EventType.ROUTE_FALLBACK if facts.get("fallback")
                          else EventType.ENDPOINT_UNHEALTHY)
        elif item.kind is ObservationKind.TASK_WARNING:
            event_type = EventType.MEMORY_UNAVAILABLE
        if event_type is None:
            return None
        failed = item.kind is ObservationKind.TASK_FAILED or facts.get("success") is False
        success = item.kind in {ObservationKind.TASK_COMPLETED,
                                ObservationKind.ADJUDICATION_COMPLETED} or facts.get("success") is True
        severity = (EventSeverity.ERROR if failed else EventSeverity.WARNING
                    if item.kind is ObservationKind.TASK_WARNING else
                    EventSeverity.SUCCESS if success else EventSeverity.ACTIVITY)
        safe_keys = ("role", "model", "node", "action", "status", "result", "reason",
                     "fallback", "optional_requested", "eligible")
        metadata = EventMetadata(tuple((key, facts[key]) for key in safe_keys
                                       if key in facts and type(facts[key]) in {str, int, float, bool, type(None)}))
        return VisualizerEvent(uuid.uuid4().hex, item.timestamp, event_type, severity,
                               "runtime", item.kind.value.replace("_", " "), item.run_id, metadata)


class VisualizerVoiceObserver:
    """VoiceLifecycle-compatible adapter into the shared runtime projection."""

    def __init__(self, runtime_observer: VisualizerRuntimeObserver):
        self.runtime_observer = runtime_observer

    def publish(self, event: VoiceLifecycleEvent) -> None:
        self.runtime_observer.publish_voice(event)
