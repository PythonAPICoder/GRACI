"""Focused Phase 5D live observer integration and isolation tests."""

import json
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path

from graci.autonomous import AutonomousRepairController
from graci.config import Config
from graci.observation import ObservationKind, observe
from graci.memory import MemoryStore
from graci.memory_governance import MemoryGovernance
from graci.phase3b import Phase3BController
from graci.provider import ProviderResponse
from graci.registry import (GLM_MODEL_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID,
                            HealthState, build_phase3a_registry)
from graci.visualizer import SystemState, serialize_visualizer
from graci.visualizer_backend import VisualizerStateProvider
from graci.visualizer_runtime import VisualizerRuntimeObserver


class SequenceProvider:
    def __init__(self, decisions): self.decisions = iter(decisions)
    def propose_repair_decision(self, task, context):
        return ProviderResponse(200, json.dumps(next(self.decisions)), QWEN_MODEL_ID)


class Reviewer:
    def review(self, context):
        result = {"schema_version": 1, "verdict": "PASS", "findings": [],
                  "rationale": "deterministic evidence accepted"}
        return ProviderResponse(200, json.dumps(result), GLM_MODEL_ID)


class RecordingProvider(VisualizerStateProvider):
    def __init__(self):
        super().__init__(); self.states = []
    def publish_snapshot(self, snapshot):
        self.states.append(snapshot.system_state)
        super().publish_snapshot(snapshot)


class RaisingObserver:
    def observe(self, observation): raise RuntimeError("visualizer unavailable")


class UnavailableGovernance:
    def select(self, request): raise OSError("vault unavailable")


def registry():
    value = build_phase3a_registry()
    endpoint = replace(value.endpoints[PRIMARY_ENDPOINT_ID],
                       health_state=HealthState.HEALTHY,
                       observed_models=(QWEN_MODEL_ID, GLM_MODEL_ID))
    return value.with_endpoint(endpoint)


class Phase5DRuntimeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.workspace = self.root / "fixture"; self.runs = self.root / "runs"
        (self.workspace / "tests").mkdir(parents=True)
        (self.workspace / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.workspace / "tests" / "test_app.py").write_text(
            "import unittest\nfrom app import VALUE\nclass T(unittest.TestCase):\n"
            " def test_value(self): self.assertEqual(VALUE, 1)\n", encoding="utf-8")

    def tearDown(self): self.temp.cleanup()

    def controller(self, observer=None, decisions=None):
        decisions = decisions or [
            {"schema_version": 1, "action": "list_files", "rationale": "inspect"},
            {"schema_version": 1, "action": "inspect_file", "target_path": "app.py", "rationale": "read"},
            {"schema_version": 1, "action": "run_tests", "rationale": "verify"}]
        return AutonomousRepairController(
            self.workspace, readable_files=("app.py", "tests/test_app.py"),
            editable_files=("app.py",), config=Config(run_directory=self.runs),
            provider=SequenceProvider(decisions), observer=observer)

    def test_real_success_lifecycle_and_exact_qwen_identity(self):
        provider = RecordingProvider(); projection = VisualizerRuntimeObserver(provider)
        result = self.controller(projection).run("Inspect and verify the fixture.")
        self.assertEqual(result["status"], "PASS")
        required = [SystemState.PLANNING, SystemState.RETRIEVING_MEMORY,
                    SystemState.REASONING, SystemState.EXECUTING_TOOL,
                    SystemState.TESTING, SystemState.COMPLETED]
        positions = [provider.states.index(state) for state in required]
        self.assertEqual(positions, sorted(positions))
        snapshot = provider.snapshot()
        self.assertEqual(snapshot.agents.qwen.model_id, QWEN_MODEL_ID)
        self.assertEqual(snapshot.agents.qwen.assigned_node, "3090-primary-localhost")
        self.assertEqual(snapshot.compute.primary_3090.assigned_role, "implementer")

    def test_optional_observer_and_raising_observer_do_not_change_result(self):
        baseline = self.controller().run("Verify.")
        isolated = self.controller(RaisingObserver()).run("Verify.")
        self.assertEqual((baseline["status"], baseline["terminal_reason"]),
                         (isolated["status"], isolated["terminal_reason"]))

    def test_controlled_failure_is_truthful(self):
        bad = [{"schema_version": 1, "action": "finish", "rationale": "not verified"}]
        provider = RecordingProvider()
        result = self.controller(VisualizerRuntimeObserver(provider), bad).run("Fail safely.")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(provider.snapshot().system_state, SystemState.FAILED)

    def test_memory_metadata_only_and_no_sensitive_payload_fields(self):
        provider = RecordingProvider(); projection = VisualizerRuntimeObserver(provider)
        observe(projection, ObservationKind.TASK_STARTED, "r1", summary="bounded")
        observe(projection, ObservationKind.MEMORY_STARTED, "r1")
        observe(projection, ObservationKind.MEMORY_COMPLETED, "r1", requested=True,
                mode="optional", relevance_keys=("project.policy",), status="MEMORY_APPLIED",
                selected_ids=("m-1",), supplied_ids=("m-1",), supplied_count=1,
                context_characters=120, conflict_count=0, corruption_count=1)
        rendered = serialize_visualizer(provider.snapshot())
        self.assertIn('"selected_memory_ids":["m-1"]', rendered)
        for prohibited in ("memory_content", "full_prompt", "chain_of_thought", "stdout", "stderr"):
            self.assertNotIn(prohibited, rendered)

    def test_real_governed_memory_selection_projects_ids_not_content(self):
        governance = MemoryGovernance(MemoryStore(
            self.root / "memory", clock=lambda: datetime.now(timezone.utc)))
        written = governance.write_explicit_user({
            "operation_id": str(uuid.uuid4()),
            "scope": {"kind": "project", "id": "phase5d"},
            "memory_type": "decision", "content": "PRIVATE-MEMORY-CONTENT",
            "source_ref": "phase5d-test", "relevance_key": "project.policy",
            "expires_at": None})
        request = {"context": {"kind": "project", "project_id": "phase5d",
                               "session_id": None, "include_global": False,
                               "include_project": False},
                   "relevance_keys": ["project.policy"],
                   "allowed_memory_types": ["decision"], "limit": 1,
                   "mode": "optional"}
        provider = RecordingProvider(); observer = VisualizerRuntimeObserver(provider)
        controller = AutonomousRepairController(
            self.workspace, readable_files=("app.py", "tests/test_app.py"),
            editable_files=("app.py",), config=Config(run_directory=self.runs),
            provider=SequenceProvider([{"schema_version": 1, "action": "run_tests",
                                        "rationale": "verify"}]),
            memory_governance=governance, memory_request=request, observer=observer)
        result = controller.run("Use governed context and verify.")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(provider.snapshot().memory.selected_memory_ids,
                         (written.memory_id,))
        self.assertNotIn("PRIVATE-MEMORY-CONTENT",
                         serialize_visualizer(provider.snapshot()))

    def test_optional_memory_unavailability_is_warning_then_execution_continues(self):
        request = {"context": {"kind": "project", "project_id": "phase5d",
                               "session_id": None, "include_global": False,
                               "include_project": False},
                   "relevance_keys": ["project.policy"],
                   "allowed_memory_types": ["decision"], "limit": 1,
                   "mode": "optional"}
        provider = RecordingProvider(); observer = VisualizerRuntimeObserver(provider)
        controller = AutonomousRepairController(
            self.workspace, readable_files=("app.py", "tests/test_app.py"),
            editable_files=("app.py",), config=Config(run_directory=self.runs),
            provider=SequenceProvider([{"schema_version": 1, "action": "run_tests",
                                        "rationale": "verify"}]),
            memory_governance=UnavailableGovernance(), memory_request=request,
            observer=observer)
        result = controller.run("Continue without optional memory.")
        self.assertEqual(result["status"], "PASS")
        self.assertIn(SystemState.WARNING, provider.states)
        self.assertEqual(provider.snapshot().system_state, SystemState.COMPLETED)

    def test_review_and_adjudication_are_distinct_with_exact_glm_identity(self):
        provider = RecordingProvider(); observer = VisualizerRuntimeObserver(provider)
        implementer = SequenceProvider([
            {"schema_version": 1, "action": "run_tests", "rationale": "verify"}])
        controller = Phase3BController(
            self.workspace, registry=registry(),
            readable_files=("app.py", "tests/test_app.py"), editable_files=("app.py",),
            run_directory=self.runs, implementer_provider=implementer,
            reviewer_provider=Reviewer(), observer=observer)
        result = controller.run("Verify with review.")
        self.assertEqual(result["status"], "PASS")
        reviewing = provider.states.index(SystemState.REVIEWING)
        adjudicating = provider.states.index(SystemState.ADJUDICATING)
        self.assertLess(reviewing, adjudicating)
        self.assertEqual(provider.snapshot().review.reviewer_model_id, GLM_MODEL_ID)
        self.assertEqual(provider.snapshot().system_state, SystemState.COMPLETED)

    def test_projector_event_buffer_remains_bounded(self):
        provider = RecordingProvider(); observer = VisualizerRuntimeObserver(provider)
        observe(observer, ObservationKind.TASK_STARTED, "r1", summary="bounded")
        for _ in range(140):
            observe(observer, ObservationKind.MODEL_STARTED, "r1", role="implementer",
                    model=QWEN_MODEL_ID, node="3090")
        self.assertEqual(len(provider.events()), 100)
        self.assertEqual(len(provider.snapshot().recent_events), 100)

    def test_4090_is_optional_and_mo2_running_facts_remain_ineligible(self):
        provider = RecordingProvider(); observer = VisualizerRuntimeObserver(provider)
        observe(observer, ObservationKind.ROUTE_COMPLETED, "route-1", role="implementer",
                model=QWEN_MODEL_ID, node="3090", optional_requested=True, fallback=True,
                eligibility={"eligible": False, "reason_code": "mo2_running",
                             "mo2": {"state": "RUNNING"},
                             "endpoint_health": {"state": "healthy"}})
        snapshot = provider.snapshot()
        self.assertEqual(snapshot.compute.primary_3090.role.value, "primary")
        self.assertEqual(snapshot.compute.optional_4090.role.value, "optional")
        self.assertFalse(snapshot.compute.optional_4090.eligible)
        self.assertEqual(snapshot.compute.optional_4090.mo2_state.value, "RUNNING")
        self.assertEqual(snapshot.compute.primary_3090.assigned_model, QWEN_MODEL_ID)


if __name__ == "__main__": unittest.main()
