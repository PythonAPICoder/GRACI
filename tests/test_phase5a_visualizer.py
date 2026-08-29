"""Focused Phase 5A visualizer contract, security, and architecture tests."""

import json
import unittest
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from graci.availability import Mo2State
from graci.registry import GLM_MODEL_ID, QWEN_MODEL_ID, HealthState, NodeRole
from graci.visualizer import (
    DISPLAY_LABEL_LIMIT, ERROR_SUMMARY_LIMIT, EVENT_MESSAGE_LIMIT,
    EVENT_SCHEMA_VERSION, RECENT_EVENT_LIMIT, SNAPSHOT_SCHEMA_VERSION,
    TASK_SUMMARY_LIMIT, ActivityState, AgentView, AgentsView, ComputeNodeView,
    ComputeView, EventMetadata, EventSeverity, EventType, ExecutionView,
    MemoryMode, MemoryView, OperationCategory, OperationView, RecentEventBuffer,
    ReviewView, SystemState, TaskView, TestView, TrustedRuntimeState,
    VisualizerEvent, WorkflowStatus, default_compute, inactive_agents,
    project_snapshot, serialize_visualizer, to_json_compatible,
)


NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)


def event(index=0, **overrides):
    values = dict(event_id=f"event-{index:03}", timestamp=NOW + timedelta(seconds=index),
                  event_type=EventType.SYSTEM_READY, severity=EventSeverity.INFO,
                  source="controller", message="Runtime fact.")
    values.update(overrides)
    return VisualizerEvent(**values)


def source(**overrides):
    values = dict(
        controller_state=SystemState.IDLE, task=TaskView(),
        compute=default_compute(), agents=inactive_agents(), memory=MemoryView(),
        execution=ExecutionView(), review=ReviewView())
    values.update(overrides)
    return TrustedRuntimeState(**values)


def snapshot(state=None, **kwargs):
    return project_snapshot(state or source(), snapshot_id="snapshot-1",
                            generated_at=NOW + timedelta(minutes=10), **kwargs)


class SnapshotContractTests(unittest.TestCase):
    def test_idle_snapshot_and_stable_versions(self):
        result = snapshot()
        self.assertEqual(result.system_state, SystemState.IDLE)
        self.assertEqual(result.schema_version, SNAPSHOT_SCHEMA_VERSION, 1)
        self.assertEqual(EVENT_SCHEMA_VERSION, 1)
        self.assertIsNone(result.task.task_id)
        self.assertEqual(result.task.final_status, WorkflowStatus.NOT_APPLICABLE)

    def test_active_task_unknown_nullable_and_bounded_summary(self):
        task = TaskView(task_id="task-1", goal_id=None, summary=" word\n" * 300,
                        started_at=NOW, phase="implementation", progress_current=2,
                        progress_total=4, final_status=WorkflowStatus.ACTIVE)
        result = snapshot(source(controller_state=SystemState.REASONING, task=task))
        self.assertEqual(result.system_state, SystemState.REASONING)
        self.assertEqual(len(result.task.summary), TASK_SUMMARY_LIMIT)
        self.assertTrue(result.task.summary.endswith("…"))
        self.assertIsNone(result.compute.optional_4090.eligible)
        self.assertIsNone(result.execution.tests.total_count)

    def test_deterministic_json_and_timezone(self):
        result = snapshot()
        first = serialize_visualizer(result)
        self.assertEqual(first, serialize_visualizer(result))
        parsed = json.loads(first)
        self.assertEqual(parsed["generated_at"], "2026-08-27T12:10:00Z")
        self.assertEqual(parsed["schema_version"], 2)
        self.assertEqual(parsed["system_state"], "idle")
        with self.assertRaises(ValueError):
            project_snapshot(source(), snapshot_id="x", generated_at=datetime(2026, 1, 1))

    def test_frozen_domain_safe_behavior_and_source_not_mutated(self):
        original = source()
        before = repr(original)
        result = snapshot(original)
        self.assertEqual(repr(original), before)
        with self.assertRaises(FrozenInstanceError):
            result.task = TaskView()  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.compute.optional_4090.eligible = True  # type: ignore[misc]

    def test_known_and_invalid_system_states(self):
        expected = {"idle", "listening", "planning", "retrieving_memory", "reasoning",
                    "executing_tool", "testing", "reviewing", "adjudicating", "completed",
                    "warning", "failed", "speaking"}
        self.assertEqual({state.value for state in SystemState}, expected)
        with self.assertRaises(ValueError):
            replace(source(), controller_state="model_says_done")  # type: ignore[arg-type]

    def test_completion_requires_deterministic_terminal_fact(self):
        unsupported = source(controller_state=SystemState.COMPLETED,
                             deterministic_terminal_status=None)
        accepted = replace(unsupported, deterministic_terminal_status="PASS")
        self.assertEqual(snapshot(unsupported).system_state, SystemState.WARNING)
        self.assertEqual(snapshot(accepted).system_state, SystemState.COMPLETED)

    def test_deterministic_failure_overrides_activity(self):
        result = snapshot(source(controller_state=SystemState.REASONING,
                                 deterministic_tests_failed=True))
        self.assertEqual(result.system_state, SystemState.FAILED)


class ComputeAndAgentTests(unittest.TestCase):
    def test_fixed_3090_and_4090_roles(self):
        compute = default_compute(primary_health=HealthState.HEALTHY,
                                  optional_health=HealthState.HEALTHY,
                                  optional_eligible=True, mo2_state=Mo2State.NOT_RUNNING,
                                  optional_reason="eligible")
        self.assertEqual(compute.primary_3090.role, NodeRole.PRIMARY)
        self.assertEqual(compute.optional_4090.role, NodeRole.OPTIONAL)
        self.assertTrue(compute.optional_4090.eligible)
        with self.assertRaises(ValueError):
            replace(compute.primary_3090, role=NodeRole.OPTIONAL)

    def test_mo2_running_truthfully_forces_ineligible_without_policy_mutation(self):
        compute = default_compute(optional_health=HealthState.HEALTHY,
                                  optional_eligible=True, mo2_state=Mo2State.RUNNING)
        self.assertFalse(compute.optional_4090.eligible)
        self.assertEqual(compute.optional_4090.availability, ActivityState.INACTIVE)
        self.assertEqual(compute.optional_4090.policy_reason, "mo2_running")
        with self.assertRaises(ValueError):
            replace(compute.optional_4090, eligible=True)

    def test_unhealthy_and_unknown_are_explicit(self):
        unhealthy = default_compute(optional_health=HealthState.UNHEALTHY,
                                    optional_eligible=False, optional_reason="endpoint_unhealthy")
        unknown = default_compute()
        self.assertEqual(unhealthy.optional_4090.endpoint_health, HealthState.UNHEALTHY)
        self.assertEqual(unhealthy.optional_4090.availability, ActivityState.FAILED)
        self.assertIsNone(unknown.optional_4090.eligible)
        self.assertEqual(unknown.optional_4090.availability, ActivityState.UNKNOWN)

    def test_qwen_and_glm_roles_nodes_and_inactive_reviewer(self):
        agents = AgentsView(
            AgentView(QWEN_MODEL_ID, "implementer", ActivityState.ACTIVE, "3090",
                      SystemState.REASONING, started_at=NOW),
            AgentView(GLM_MODEL_ID, "reviewer", ActivityState.INACTIVE,
                      review_status=WorkflowStatus.NOT_APPLICABLE))
        self.assertEqual(agents.qwen.assigned_node, "3090")
        self.assertEqual(agents.glm.model_id, GLM_MODEL_ID)
        self.assertEqual(agents.glm.review_status, WorkflowStatus.NOT_APPLICABLE)
        self.assertNotIn("reasoning_text", {field.name for field in fields(AgentView)})
        self.assertNotIn("chain_of_thought", {field.name for field in fields(AgentView)})


class MemoryExecutionReviewTests(unittest.TestCase):
    def test_memory_metadata_only_with_modes_and_counts(self):
        memory = MemoryView(True, MemoryMode.REQUIRED, ("project.graci.policy",), "MEMORY_APPLIED",
                            ("memory-1", "memory-2"), ("memory-1",), 1, 512, 2, 3)
        rendered = to_json_compatible(snapshot(source(memory=memory)))
        self.assertEqual(rendered["memory"]["selected_memory_ids"], ["memory-1", "memory-2"])
        self.assertEqual(rendered["memory"]["conflict_count"], 2)
        self.assertEqual(rendered["memory"]["corruption_count"], 3)
        names = {field.name for field in fields(MemoryView)}
        self.assertTrue({"mode", "selected_memory_ids", "supplied_memory_ids"} <= names)
        self.assertTrue({"content", "records", "vault", "raw_data"}.isdisjoint(names))
        with self.assertRaises(ValueError):
            MemoryView(False, MemoryMode.OPTIONAL)

    def test_tool_activity_and_failed_tool_are_bounded(self):
        active = OperationView(OperationCategory.EDIT, WorkflowStatus.ACTIVE,
                               started_at=NOW, target_label="src/app.py")
        failed = OperationView(OperationCategory.COMMAND, WorkflowStatus.FAILED,
                               started_at=NOW, completed_at=NOW, error_code="exit_1",
                               error_reason="x" * 1000)
        execution = ExecutionView((active, failed))
        self.assertEqual(len(execution.operations[1].error_reason), ERROR_SUMMARY_LIMIT)
        self.assertNotIn("stdout", {field.name for field in fields(OperationView)})
        self.assertNotIn("stderr", {field.name for field in fields(OperationView)})

    def test_passing_and_failing_test_truth(self):
        passed = TestView(WorkflowStatus.PASSED, "warning-strict suite", 10, 0, 10, 1200)
        failed = TestView(WorkflowStatus.FAILED, "warning-strict suite", 9, 1, 10, 1100,
                          "assertion_failed")
        self.assertEqual(passed.status, WorkflowStatus.PASSED)
        self.assertEqual(failed.failed_count, 1)
        with self.assertRaises(ValueError):
            TestView(WorkflowStatus.PASSED, passed_count=9, failed_count=1, total_count=10)

    def test_review_and_deterministic_adjudication_are_separate(self):
        review = ReviewView(True, GLM_MODEL_ID, WorkflowStatus.PASSED, "PASS", 0,
                            WorkflowStatus.PASSED, "PASS", "tests_passed_and_review_passed")
        rejected = replace(review, structured_verdict="PASS",
                           adjudication_status=WorkflowStatus.REJECTED,
                           final_outcome="REVIEW_ERROR", reason_code="invalid_evidence")
        self.assertEqual(rejected.structured_verdict, "PASS")
        self.assertEqual(rejected.adjudication_status, WorkflowStatus.REJECTED)
        self.assertNotIn("rationale", {field.name for field in fields(ReviewView)})
        with self.assertRaises(ValueError):
            ReviewView(False, reviewer_status=WorkflowStatus.PASSED)


class EventContractTests(unittest.TestCase):
    def test_valid_immutable_serializable_event_without_task(self):
        item = event(message="  bounded\nmessage  ", metadata=EventMetadata((('node', '3090'),)))
        self.assertIsNone(item.task_id)
        self.assertEqual(item.message, "bounded message")
        self.assertEqual(json.loads(serialize_visualizer(item))["metadata"], {"node": "3090"})
        with self.assertRaises(FrozenInstanceError):
            item.message = "changed"  # type: ignore[misc]

    def test_enum_validation_and_message_bound(self):
        item = event(message="m" * 1000)
        self.assertEqual(len(item.message), EVENT_MESSAGE_LIMIT)
        with self.assertRaises(ValueError):
            event(severity="catastrophic")
        with self.assertRaises(ValueError):
            event(event_type="made_up")

    def test_metadata_is_bounded_sorted_and_rejects_sensitive_or_structured_values(self):
        metadata = EventMetadata((("z", "v" * 1000), ("a", 1)))
        self.assertEqual(metadata.entries[0], ("a", 1))
        self.assertEqual(len(metadata.entries[1][1]), 160)
        with self.assertRaises(ValueError):
            EventMetadata((("api_token", "secret"),))
        with self.assertRaises(ValueError):
            EventMetadata((("raw", {"unbounded": "value"}),))

    def test_unique_ordered_bounded_buffer_and_oldest_eviction(self):
        buffer = RecentEventBuffer(capacity=3)
        for index in range(4):
            buffer = buffer.append(event(index), observed_at=NOW + timedelta(minutes=1))
        self.assertEqual([item.event_id for item in buffer.events],
                         ["event-001", "event-002", "event-003"])
        with self.assertRaises(ValueError):
            buffer.append(event(3), observed_at=NOW + timedelta(minutes=1))
        with self.assertRaises(ValueError):
            buffer.append(event(2, event_id="older"), observed_at=NOW + timedelta(minutes=1))
        self.assertEqual(RECENT_EVENT_LIMIT, 100)

    def test_future_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            RecentEventBuffer().append(event(), observed_at=NOW - timedelta(seconds=1))


class SecurityArchitectureTests(unittest.TestCase):
    def test_snapshot_schema_excludes_sensitive_content_and_authority_methods(self):
        serialized = serialize_visualizer(snapshot())
        prohibited = ("full_prompt", "prompt", "chain_of_thought", "reasoning_text",
                      "memory_content", "stdout", "stderr", "environment", "credential")
        for term in prohibited:
            self.assertNotIn(term, serialized)
        methods = set(dir(snapshot()))
        self.assertTrue({"run_tool", "write_memory", "route", "approve", "submit_task"}.isdisjoint(methods))

    def test_secret_looking_runtime_metadata_not_blindly_projected(self):
        with self.assertRaises(ValueError):
            EventMetadata((("password", "do-not-display"),))
        with self.assertRaises(ValueError):
            EventMetadata((("private_key", "do-not-display"),))

    def test_projection_does_not_import_backend_ui_or_capability_modules(self):
        path = Path(__file__).resolve().parents[1] / "graci" / "visualizer.py"
        text = path.read_text(encoding="utf-8")
        for forbidden in ("urllib", "subprocess", "socket", "http.server", "websocket",
                          "from .tools", "from .memory import", "from .provider"):
            self.assertNotIn(forbidden, text)
        for core_name in ("controller.py", "routing.py", "availability.py", "memory.py"):
            core = (path.parent / core_name).read_text(encoding="utf-8")
            self.assertNotIn("visualizer", core.lower())

    def test_display_bounds_are_stable(self):
        self.assertEqual((TASK_SUMMARY_LIMIT, EVENT_MESSAGE_LIMIT, ERROR_SUMMARY_LIMIT,
                          DISPLAY_LABEL_LIMIT), (240, 320, 240, 160))


class EvidenceTests(unittest.TestCase):
    def test_phase5a_acceptance_evidence(self):
        path = Path(__file__).resolve().parents[1] / "phase5a" / "evidence" / "phase5a-acceptance.json"
        evidence = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["starting_commit"], "7ddf51c7fd55fd9e2f4c5fee74a8c18445f40bb3")
        self.assertEqual(evidence["snapshot_schema_version"], 1)
        self.assertEqual(evidence["event_schema_version"], 1)
        self.assertEqual(evidence["status"], "PASS")
        self.assertTrue(all(evidence["checks"].values()))
        self.assertEqual(evidence["privacy"]["cloud_ai_usage"], "none")


if __name__ == "__main__":
    unittest.main()
