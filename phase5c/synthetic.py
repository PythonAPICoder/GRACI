"""Trusted in-process Phase 5C fixtures with no HTTP publication or core mutation."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from graci.availability import Mo2State
from graci.registry import GLM_MODEL_ID, QWEN_MODEL_ID, HealthState
from graci.visualizer import (
    ActivityState, AgentView, AgentsView, EventSeverity, EventType, ExecutionView,
    MemoryMode, MemoryView, OperationCategory, OperationView, ReviewView, SystemState,
    TaskView, TestView, TrustedRuntimeState, VisualizerEvent, WorkflowStatus,
    default_compute, inactive_agents, project_snapshot,
)

STATES = (SystemState.IDLE, SystemState.PLANNING, SystemState.RETRIEVING_MEMORY,
          SystemState.REASONING, SystemState.EXECUTING_TOOL, SystemState.TESTING,
          SystemState.REVIEWING, SystemState.ADJUDICATING, SystemState.COMPLETED,
          SystemState.WARNING, SystemState.FAILED, SystemState.LISTENING,
          SystemState.SPEAKING)
EVENT_TYPES = (EventType.SYSTEM_IDLE, EventType.TASK_STARTED, EventType.MEMORY_REQUESTED,
               EventType.QWEN_STARTED, EventType.TOOL_STARTED, EventType.TESTS_STARTED,
               EventType.REVIEW_STARTED, EventType.ADJUDICATION_COMPLETED,
               EventType.TASK_COMPLETED, EventType.NODE_INELIGIBLE, EventType.TASK_FAILED)


def lifecycle(*, blocked_4090: bool = False, now: datetime | None = None):
    """Return immutable snapshots/events. Publication remains a caller-owned internal act."""
    base = now or datetime.now(timezone.utc)
    if base.tzinfo is None:
        raise ValueError("now must be timezone aware")
    task = TaskView("phase5c-visual-acceptance", "phase5c", "Render the observer-only command center UI.",
                    base, "Phase 5C", 0, 9, WorkflowStatus.ACTIVE)
    compute = default_compute(primary_health=HealthState.HEALTHY,
                              optional_health=HealthState.HEALTHY,
                              optional_eligible=not blocked_4090,
                              mo2_state=Mo2State.RUNNING if blocked_4090 else Mo2State.NOT_RUNNING,
                              optional_reason="mo2_running" if blocked_4090 else "eligible")
    empty = TrustedRuntimeState(SystemState.IDLE, TaskView(), compute, inactive_agents(),
                                MemoryView(), ExecutionView(), ReviewView())
    snapshots = []
    for index, system_state in enumerate(STATES):
        if system_state is SystemState.IDLE:
            source = empty
        else:
            progress = min(index, 9)
            current_task = replace(task, progress_current=progress,
                                   final_status=(WorkflowStatus.PASSED if system_state is SystemState.COMPLETED
                                                 else WorkflowStatus.FAILED if system_state is SystemState.FAILED
                                                 else WorkflowStatus.ACTIVE),
                                   failure_reason="Synthetic bounded failure for visual acceptance." if system_state is SystemState.FAILED else None)
            memory = (MemoryView(True, MemoryMode.OPTIONAL, ("project.graci.phase5c", "visualizer.command_center"),
                                 "MEMORY_APPLIED", ("memory-visual-1", "memory-visual-2"),
                                 ("memory-visual-1", "memory-visual-2"), 2, 3840, 0, 0)
                      if index >= 2 else MemoryView())
            qwen = AgentView(QWEN_MODEL_ID, "implementer / general reasoning",
                             ActivityState.COMPLETED if index >= 6 else ActivityState.ACTIVE,
                             "3090", SystemState.REASONING if index >= 3 else system_state, started_at=base)
            glm = AgentView(GLM_MODEL_ID, "reviewer / verifier",
                            ActivityState.ACTIVE if 6 <= index < 8 else ActivityState.COMPLETED if index >= 8 else ActivityState.INACTIVE,
                            "3090" if index >= 6 else None, SystemState.REVIEWING if index >= 6 else None,
                            WorkflowStatus.PASSED if index >= 8 else WorkflowStatus.ACTIVE if index >= 6 else WorkflowStatus.NOT_APPLICABLE)
            operations = () if index < 4 else (
                OperationView(OperationCategory.EDIT, WorkflowStatus.PASSED, base, base + timedelta(milliseconds=840), "graci/visualizer_ui/visualizer.js"),
                OperationView(OperationCategory.VERIFY, WorkflowStatus.ACTIVE if index == 4 else WorkflowStatus.PASSED, base, None if index == 4 else base + timedelta(seconds=2), "Phase 5C static surface"),
            )
            tests = TestView(WorkflowStatus.ACTIVE if index == 5 else WorkflowStatus.PASSED if index >= 6 else WorkflowStatus.NOT_APPLICABLE,
                             "warning-strict repository suite" if index >= 5 else None,
                             188 if index >= 6 else None, 0 if index >= 6 else None, 188 if index >= 6 else None, 921 if index >= 6 else None)
            review = ReviewView(index >= 6, GLM_MODEL_ID if index >= 6 else None,
                                WorkflowStatus.PASSED if index >= 7 else WorkflowStatus.ACTIVE if index >= 6 else WorkflowStatus.NOT_APPLICABLE,
                                "PASS" if index >= 7 else None, 0,
                                WorkflowStatus.PASSED if index >= 8 else WorkflowStatus.ACTIVE if index == 7 else WorkflowStatus.NOT_APPLICABLE,
                                "PASS" if index >= 8 else None, "deterministic_acceptance" if index >= 8 else None)
            source = TrustedRuntimeState(system_state, current_task, compute, AgentsView(qwen, glm),
                                         memory, ExecutionView(operations, tests), review,
                                         deterministic_tests_failed=system_state is SystemState.FAILED,
                                         deterministic_terminal_status="PASS" if system_state is SystemState.COMPLETED else "FAIL" if system_state is SystemState.FAILED else None)
        snapshots.append(project_snapshot(source, snapshot_id=f"phase5c-{system_state.value}", generated_at=base + timedelta(milliseconds=index)))
    events = tuple(VisualizerEvent(f"phase5c-event-{i:02}", base + timedelta(milliseconds=i), kind,
                                   EventSeverity.ERROR if i == 10 else EventSeverity.WARNING if i == 9 else EventSeverity.SUCCESS if i in {7,8} else EventSeverity.ACTIVITY,
                                   "synthetic-controller", f"Synthetic {kind.value.replace('_', ' ')}.", task.task_id)
                   for i, kind in enumerate(EVENT_TYPES))
    return tuple(snapshots), events
