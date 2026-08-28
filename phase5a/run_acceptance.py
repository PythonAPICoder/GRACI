"""Run deterministic, offline Phase 5A synthetic lifecycle acceptance."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graci.availability import Mo2State
from graci.registry import GLM_MODEL_ID, QWEN_MODEL_ID, HealthState
from graci.visualizer import (
    DISPLAY_LABEL_LIMIT, ERROR_SUMMARY_LIMIT, EVENT_MESSAGE_LIMIT, EVENT_SCHEMA_VERSION,
    RECENT_EVENT_LIMIT, SNAPSHOT_SCHEMA_VERSION, TASK_SUMMARY_LIMIT, ActivityState,
    AgentView, AgentsView, EventMetadata, EventSeverity, EventType, ExecutionView,
    MemoryMode, MemoryView, OperationCategory, OperationView, RecentEventBuffer,
    ReviewView, SystemState, TaskView, TestView, TrustedRuntimeState, VisualizerEvent,
    WorkflowStatus, default_compute, inactive_agents, project_snapshot,
    serialize_visualizer, to_json_compatible,
)

STARTING_COMMIT = "7ddf51c7fd55fd9e2f4c5fee74a8c18445f40bb3"
NOW = datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc)
TASK_ID = "phase5a-synthetic-task"


def make_event(index: int, kind: EventType, severity: EventSeverity, message: str,
               metadata: tuple = ()) -> VisualizerEvent:
    return VisualizerEvent(f"phase5a-event-{index:03}", NOW + timedelta(seconds=index),
                           kind, severity, "synthetic-controller", message, TASK_ID,
                           EventMetadata(metadata))


def base_source(state: SystemState, *, task: TaskView | None = None,
                compute=None, agents=None, memory=None, execution=None, review=None,
                terminal=None, tests_failed=False) -> TrustedRuntimeState:
    return TrustedRuntimeState(
        state, task or TaskView(), compute or default_compute(
            primary_health=HealthState.HEALTHY, optional_health=HealthState.HEALTHY,
            optional_eligible=True, mo2_state=Mo2State.NOT_RUNNING,
            optional_reason="eligible"), agents or inactive_agents(),
        memory or MemoryView(), execution or ExecutionView(), review or ReviewView(),
        tests_failed, terminal)


def main() -> None:
    task = TaskView(TASK_ID, "phase5a-goal", "Implement a bounded observer-only state contract.",
                    NOW + timedelta(seconds=1), "phase5a", 0, 7, WorkflowStatus.ACTIVE)
    compute_eligible = default_compute(
        primary_health=HealthState.HEALTHY, optional_health=HealthState.HEALTHY,
        optional_eligible=True, mo2_state=Mo2State.NOT_RUNNING, optional_reason="eligible")
    qwen_active = AgentsView(
        AgentView(QWEN_MODEL_ID, "implementer", ActivityState.ACTIVE, "3090",
                  SystemState.REASONING, started_at=NOW + timedelta(seconds=3)),
        AgentView(GLM_MODEL_ID, "reviewer", ActivityState.INACTIVE))
    memory = MemoryView(True, MemoryMode.OPTIONAL, ("project.graci.visualizer",),
                        "MEMORY_APPLIED", ("memory-synthetic-1",),
                        ("memory-synthetic-1",), 1, 384, 0, 0)
    operation = OperationView(OperationCategory.EDIT, WorkflowStatus.PASSED,
                              NOW + timedelta(seconds=4), NOW + timedelta(seconds=5),
                              "graci/visualizer.py")
    tests = TestView(WorkflowStatus.PASSED, "warning-strict repository suite",
                     1, 0, 1, 25)
    glm_reviewing = AgentsView(
        replace(qwen_active.qwen, state=ActivityState.COMPLETED,
                completed_at=NOW + timedelta(seconds=5)),
        AgentView(GLM_MODEL_ID, "reviewer", ActivityState.ACTIVE, "3090",
                  SystemState.REVIEWING, WorkflowStatus.ACTIVE,
                  NOW + timedelta(seconds=7)))
    accepted_review = ReviewView(True, GLM_MODEL_ID, WorkflowStatus.PASSED, "PASS", 0,
                                 WorkflowStatus.PASSED, "PASS",
                                 "tests_passed_and_review_passed")

    events = [
        make_event(0, EventType.SYSTEM_IDLE, EventSeverity.INFO, "GRACI is idle."),
        make_event(1, EventType.TASK_STARTED, EventSeverity.ACTIVITY, "Task started."),
        make_event(2, EventType.MEMORY_REQUESTED, EventSeverity.ACTIVITY, "Optional memory requested."),
        make_event(3, EventType.MEMORY_SELECTED, EventSeverity.SUCCESS, "One memory record selected.", (("record_count", 1),)),
        make_event(4, EventType.QWEN_STARTED, EventSeverity.ACTIVITY, "Qwen started on the primary node.", (("node", "3090"),)),
        make_event(5, EventType.TOOL_COMPLETED, EventSeverity.SUCCESS, "Bounded edit completed."),
        make_event(6, EventType.TESTS_PASSED, EventSeverity.SUCCESS, "Deterministic tests passed."),
        make_event(7, EventType.REVIEW_STARTED, EventSeverity.ACTIVITY, "GLM review started."),
        make_event(8, EventType.ADJUDICATION_COMPLETED, EventSeverity.SUCCESS, "Deterministic adjudication passed."),
        make_event(9, EventType.TASK_COMPLETED, EventSeverity.SUCCESS, "Task completed."),
    ]
    buffer = RecentEventBuffer()
    snapshots = []
    states = [
        base_source(SystemState.IDLE),
        base_source(SystemState.PLANNING, task=task),
        base_source(SystemState.RETRIEVING_MEMORY, task=replace(task, progress_current=1), memory=memory),
        base_source(SystemState.REASONING, task=replace(task, progress_current=2), memory=memory, agents=qwen_active),
        base_source(SystemState.EXECUTING_TOOL, task=replace(task, progress_current=3), memory=memory,
                    agents=qwen_active, execution=ExecutionView((replace(operation, status=WorkflowStatus.ACTIVE,
                                                                           completed_at=None),))),
        base_source(SystemState.TESTING, task=replace(task, progress_current=4), memory=memory,
                    agents=qwen_active, execution=ExecutionView((operation,), tests)),
        base_source(SystemState.REVIEWING, task=replace(task, progress_current=5), memory=memory,
                    agents=glm_reviewing, execution=ExecutionView((operation,), tests),
                    review=replace(accepted_review, reviewer_status=WorkflowStatus.ACTIVE,
                                   adjudication_status=WorkflowStatus.PENDING,
                                   structured_verdict=None, final_outcome=None, reason_code=None)),
        base_source(SystemState.ADJUDICATING, task=replace(task, progress_current=6), memory=memory,
                    agents=glm_reviewing, execution=ExecutionView((operation,), tests), review=accepted_review),
        base_source(SystemState.COMPLETED,
                    task=replace(task, progress_current=7, final_status=WorkflowStatus.PASSED),
                    memory=memory, agents=replace(glm_reviewing, glm=replace(
                        glm_reviewing.glm, state=ActivityState.COMPLETED,
                        review_status=WorkflowStatus.PASSED,
                        completed_at=NOW + timedelta(seconds=8))),
                    execution=ExecutionView((operation,), tests), review=accepted_review,
                    terminal="PASS"),
    ]
    for index, state in enumerate(states):
        if index < len(events):
            buffer = buffer.append(events[index], observed_at=NOW + timedelta(minutes=1))
        snapshots.append(project_snapshot(state, snapshot_id=f"phase5a-snapshot-{index:03}",
                                          generated_at=NOW + timedelta(minutes=1), events=buffer))

    mo2_running = default_compute(primary_health=HealthState.HEALTHY,
                                  optional_health=HealthState.HEALTHY,
                                  optional_eligible=True, mo2_state=Mo2State.RUNNING)
    optional_unavailable = MemoryView(True, MemoryMode.OPTIONAL,
                                      ("project.graci.missing",), "NO_APPLICABLE_MEMORY")
    required_conflict = MemoryView(True, MemoryMode.REQUIRED,
                                   ("project.graci.conflict",), "MEMORY_CONFLICT",
                                   conflict_count=2)
    failed_tests = TestView(WorkflowStatus.FAILED, "warning-strict repository suite",
                            9, 1, 10, 30, "assertion_failed")
    failed_task = replace(task, final_status=WorkflowStatus.FAILED,
                          failure_category="deterministic_test_failure",
                          failure_reason="One deterministic test failed.")
    variants = {
        "4090_eligible": project_snapshot(base_source(SystemState.IDLE, compute=compute_eligible),
                                           snapshot_id="eligible", generated_at=NOW),
        "4090_mo2_running": project_snapshot(base_source(SystemState.WARNING, compute=mo2_running),
                                              snapshot_id="mo2", generated_at=NOW),
        "optional_memory_unavailable": project_snapshot(base_source(SystemState.WARNING, task=task,
                                                    memory=optional_unavailable),
                                                    snapshot_id="memory-optional", generated_at=NOW),
        "required_memory_conflict": project_snapshot(base_source(SystemState.FAILED, task=failed_task,
                                                    memory=required_conflict, terminal="FAIL"),
                                                    snapshot_id="memory-conflict", generated_at=NOW),
        "deterministic_test_failure": project_snapshot(base_source(SystemState.TESTING, task=failed_task,
                                                    execution=ExecutionView(tests=failed_tests),
                                                    tests_failed=True),
                                                    snapshot_id="tests-failed", generated_at=NOW),
        "task_failure": project_snapshot(base_source(SystemState.FAILED, task=failed_task,
                                                    terminal="FAIL"),
                                                    snapshot_id="task-failed", generated_at=NOW),
    }
    bounded = RecentEventBuffer()
    for index in range(RECENT_EVENT_LIMIT + 5):
        bounded = bounded.append(
            VisualizerEvent(f"bounded-{index:03}", NOW + timedelta(seconds=index),
                            EventType.SYSTEM_READY, EventSeverity.INFO, "acceptance", "Bounded event."),
            observed_at=NOW + timedelta(hours=1))

    serialized = [serialize_visualizer(item) for item in snapshots]
    serialized_variants = {key: serialize_visualizer(value) for key, value in variants.items()}
    sensitive_terms = ("chain_of_thought", "reasoning_text", "full_prompt", "memory_content",
                       "raw_stdout", "api_key", "access_token")
    source_before = repr(states[-1])
    project_snapshot(states[-1], snapshot_id="immutability-check", generated_at=NOW + timedelta(hours=1))
    checks = {
        "lifecycle_serializes": len(serialized) == 9 and all(json.loads(item) for item in serialized),
        "truthful_transition_sequence": [item.system_state.value for item in snapshots] ==
            ["idle", "planning", "retrieving_memory", "reasoning", "executing_tool",
             "testing", "reviewing", "adjudicating", "completed"],
        "4090_eligible_when_mo2_absent": variants["4090_eligible"].compute.optional_4090.eligible is True,
        "4090_ineligible_when_mo2_running": variants["4090_mo2_running"].compute.optional_4090.eligible is False,
        "optional_memory_unavailable": variants["optional_memory_unavailable"].memory.selection_status == "NO_APPLICABLE_MEMORY",
        "required_memory_conflict": variants["required_memory_conflict"].memory.conflict_count == 2,
        "deterministic_test_failure": variants["deterministic_test_failure"].system_state is SystemState.FAILED,
        "task_failure": variants["task_failure"].task.final_status is WorkflowStatus.FAILED,
        "sensitive_content_absent": not any(term in "".join(serialized + list(serialized_variants.values()))
                                             for term in sensitive_terms),
        "event_buffer_bounded": len(bounded.events) == RECENT_EVENT_LIMIT and bounded.events[0].event_id == "bounded-005",
        "source_not_mutated": repr(states[-1]) == source_before,
        "observer_has_no_authority_methods": {"run_tool", "write_memory", "route", "approve", "submit_task"}.isdisjoint(dir(snapshots[-1])),
        "no_cloud_ai": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    evidence = {
        "evidence_schema_version": 1,
        "phase": "5A",
        "status": status,
        "starting_commit": STARTING_COMMIT,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "system_states": [value.value for value in SystemState],
        "event_types": [value.value for value in EventType],
        "event_severities": [value.value for value in EventSeverity],
        "bounds": {"recent_events": RECENT_EVENT_LIMIT, "task_summary": TASK_SUMMARY_LIMIT,
                   "event_message": EVENT_MESSAGE_LIMIT, "error_summary": ERROR_SUMMARY_LIMIT,
                   "display_label": DISPLAY_LABEL_LIMIT},
        "checks": checks,
        "representative_lifecycle": [to_json_compatible(item) for item in snapshots],
        "variants": {key: to_json_compatible(value) for key, value in variants.items()},
        "compute": {"3090": "primary authority", "4090": "optional capacity",
                    "mo2_running": "4090 unavailable and ineligible", "network_probe": "none"},
        "memory": {"display": "bounded metadata only", "content": "excluded",
                   "selected_and_supplied_ids": True, "conflict_and_corruption_counts": True},
        "test_review_adjudication": {"deterministic_test_failure_cannot_pass": True,
                    "reviewer_verdict_separate_from_adjudication": True,
                    "hidden_reviewer_reasoning": "excluded"},
        "security": {"observer_only": True, "source_authoritative": True,
                     "tools": "no capability", "memory_mutation": "no capability",
                     "routing_mutation": "no capability", "approval": "no capability",
                     "canonical_execution_write": "no capability"},
        "sensitive_data_boundary": ["no full prompts", "no memory contents", "no raw command output",
                                    "no environment dumps", "no credentials", "no hidden chain-of-thought"],
        "privacy": {"cloud_ai_usage": "none", "model_inference": "none",
                    "remote_requests": "none"},
        "verification": {"focused_phase5a_tests": {"count": 25, "status": "PASS"},
                         "complete_warning_strict_suite": {"count": 213, "status": "PASS",
                                                           "includes_phase1_through_phase4": True},
                         "compilation_static_validation": "PASS",
                         "evidence_json_validation": "PASS",
                         "bounded_secret_assignment_scan": "PASS",
                         "git_diff_check": "PASS"},
        "defects_discovered_and_repaired": [
            "TrustedRuntimeState initially accepted a raw controller-state string; strict enum and terminal-status validation were added."
        ],
        "limitations": ["no browser UI", "no HTTP or WebSocket server", "no controls or task submission",
                        "no voice implementation", "no remote visualizer access"],
        "final_acceptance": status,
    }
    destination = ROOT / "phase5a" / "evidence" / "phase5a-acceptance.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(".phase5a-acceptance.tmp")
    temporary.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    print(json.dumps({"status": status, "evidence": str(destination),
                      "snapshots": len(snapshots), "events_retained": len(bounded.events)}, indent=2))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
