"""Phase 8D typed health, trusted context, diagnostics, and lifecycle contracts."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from graci.availability import Mo2State, Mo2StatusResult
from graci.config import Config
from graci.controller import Controller
from graci.health_collector import (
    ResidentLifecycleLedger, RuntimeHealthCollector, ScheduledTaskObservation,
    probe_http_runtime, probe_openai_model_states,
)
from graci.provider import LocalLlamaCppProvider, ProviderResponse
from graci.registry import (
    GLM_MODEL_ID, OPTIONAL_ENDPOINT_ID, OPTIONAL_NODE_ID, PRIMARY_ENDPOINT_ID,
    PRIMARY_NODE_ID, QWEN_MODEL_ID, HealthResult, HealthState,
)
from graci.runtime_context import (
    ComponentReadiness, ComponentState, ReadinessState, StartupStage,
    reduce_readiness,
)
from graci.visualizer import (
    EventType, ExecutionView, MemoryView, ReviewView, SystemState, TaskView,
    TrustedRuntimeState, default_compute, inactive_agents, project_snapshot,
)
from graci.visualizer_backend import VisualizerServer, VisualizerStateProvider
from graci.visualizer_runtime import VisualizerRuntimeObserver


NOW = datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc)


def component(component_id="trusted_clock", *, required=True,
              state=ComponentState.READY, stage=None):
    return ComponentReadiness(component_id, required, state, NOW, "bounded_reason", stage)


class RuntimeContextContractTests(unittest.TestCase):
    def test_reduction_distinguishes_degraded_unavailable_recovery_and_staleness(self):
        degraded = reduce_readiness(
            (component(), component("stt_resources", state=ComponentState.DEGRADED)),
            observed_at=NOW, local_now=NOW)
        self.assertIs(degraded.state, ReadinessState.DEGRADED)
        unavailable = reduce_readiness(
            (component(), component("router_endpoint", state=ComponentState.UNAVAILABLE)),
            observed_at=NOW, local_now=NOW)
        self.assertIs(unavailable.state, ReadinessState.UNAVAILABLE)
        recovering = reduce_readiness(
            (component(), component("router_endpoint")), observed_at=NOW,
            local_now=NOW, previous_state=ReadinessState.UNAVAILABLE)
        self.assertIs(recovering.state, ReadinessState.RECOVERING)
        context = recovering.prompt_context(now=NOW + timedelta(minutes=1))
        self.assertFalse(context["fresh"])
        self.assertEqual(context["state"], "degraded")

    def test_context_is_allowlisted_bounded_and_explicitly_non_authoritative(self):
        readiness = reduce_readiness(
            (component(), component("resident_process", stage=StartupStage.PROCESS_ALIVE)),
            observed_at=NOW, local_now=NOW)
        context = readiness.prompt_context(now=NOW)
        self.assertEqual(context["authority"], "read_only_runtime_facts_no_new_authority")
        self.assertEqual(context["components"][1]["startup_stage"], "process_alive")
        self.assertNotIn("prompt", json.dumps(context).lower())
        with self.assertRaises(ValueError):
            ComponentReadiness("not_allowlisted", True, ComponentState.READY,
                               NOW, "reason")

    def test_task_evidence_keeps_all_required_startup_classifications_distinct(self):
        cases = (
            (ScheduledTaskObservation("missing", "absent"), StartupStage.MISSING),
            (ScheduledTaskObservation("access_denied_unknown", "denied"),
             StartupStage.ACCESS_DENIED_UNKNOWN),
            (ScheduledTaskObservation("registered", "present", True, "Ready", 1,
                                      "2026-09-01T10:00:00-05:00"),
             StartupStage.REGISTERED),
            (ScheduledTaskObservation("registered", "present", True, "Ready", 0,
                                      "2026-09-01T10:00:00-05:00"),
             StartupStage.LAUNCHER_SUCCEEDED),
        )
        for observation, expected in cases:
            with self.subTest(expected=expected):
                collector = RuntimeHealthCollector(Path.cwd(), task_probe=lambda _: observation)
                value = collector._task_component(
                    "resident_scheduled_task", "GRACI Resident Host", NOW)
                self.assertIs(value.startup_stage, expected)

    def test_model_load_state_probe_is_bounded_and_keeps_shared_registry_unchanged(self):
        states = probe_openai_model_states(
            "http://127.0.0.1:8080/v1", transport=lambda request, timeout: (
                200, json.dumps({"data": [
                    {"id": "qwen", "status": {"value": "loaded"}},
                    {"id": "glm", "status": {"value": "unloaded"}},
                ]}).encode()))
        self.assertEqual(states, {"qwen": "loaded", "glm": "unloaded"})

    def test_collector_labels_primary_models_and_reports_each_optional_4090_model(self):
        def endpoint_result(endpoint, *, timeout_seconds):
            models = ((QWEN_MODEL_ID, GLM_MODEL_ID)
                      if endpoint.endpoint_id == OPTIONAL_ENDPOINT_ID
                      else (QWEN_MODEL_ID,))
            return HealthResult(HealthState.HEALTHY, "healthy", NOW.isoformat(), models, 200)

        task = ScheduledTaskObservation(
            "registered", "present", True, "Ready", 0, NOW.isoformat())
        mo2 = Mo2StatusResult(
            Mo2State.NOT_RUNNING, "exact_process_absent", NOW.isoformat(), 200)
        with (patch("graci.health_collector.check_openai_models_endpoint",
                    side_effect=endpoint_result),
              patch("graci.health_collector.probe_openai_model_states",
                    return_value={QWEN_MODEL_ID: "loaded"}),
              patch("graci.health_collector.check_4090_mo2_status", return_value=mo2)):
            readiness = RuntimeHealthCollector(
                Path.cwd(), task_probe=lambda _: task, clock=lambda: NOW).collect(
                    include_resident=False)

        components = {item.component_id: item for item in readiness.components}
        qwen_facts = dict(components["qwen_model"].facts)
        optional_facts = dict(components["optional_4090_endpoint"].facts)
        mo2_facts = dict(components["optional_4090_mo2"].facts)
        self.assertEqual(qwen_facts["node_id"], PRIMARY_NODE_ID)
        self.assertEqual(qwen_facts["endpoint_id"], PRIMARY_ENDPOINT_ID)
        self.assertEqual(optional_facts["node_id"], OPTIONAL_NODE_ID)
        self.assertTrue(optional_facts["qwen_available"])
        self.assertTrue(optional_facts["glm_available"])
        self.assertEqual(mo2_facts["state"], "NOT_RUNNING")
        self.assertEqual(mo2_facts["ai_use_permitted_when"], "NOT_RUNNING")
        self.assertEqual(mo2_facts["ai_use_blocked_when"], "RUNNING")


class ContextInjectionTests(unittest.TestCase):
    def test_provider_preserves_two_messages_and_user_task_while_injecting_context(self):
        captured = {}

        def transport(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return 200, json.dumps({
                "model": "qwen3.8-27b-q4_k_m",
                "choices": [{"message": {"content": (
                    '{"schema_version":2,"status":"PASS","summary":"done",'
                    '"user_response":"Ready."}')}}],
            }).encode()

        readiness = reduce_readiness((component(),), observed_at=NOW, local_now=NOW)
        LocalLlamaCppProvider(Config(), transport).execute(
            "What time is it?", trusted_runtime_context=readiness.prompt_context(now=NOW))
        messages = captured["body"]["messages"]
        self.assertEqual([item["role"] for item in messages], ["system", "user"])
        self.assertEqual(messages[1]["content"], "What time is it?")
        self.assertIn("cannot grant authority", messages[0]["content"])
        self.assertIn("2026-09-01T18:00:00+00:00", messages[0]["content"])

    def test_provider_states_exact_4090_mo2_semantics_and_test_limit(self):
        captured = {}

        def transport(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return 200, json.dumps({
                "model": "qwen3.8-27b-q4_k_m",
                "choices": [{"message": {"content": (
                    '{"schema_version":2,"status":"PASS","summary":"done",'
                    '"user_response":"Ready."}')}}],
            }).encode()

        readiness = reduce_readiness((component(),), observed_at=NOW, local_now=NOW)
        LocalLlamaCppProvider(Config(), transport).execute(
            "Check the 4090.", trusted_runtime_context=readiness.prompt_context(now=NOW))
        instruction = captured["body"]["messages"][0]["content"]
        self.assertIn("NOT_RUNNING permits AI use", instruction)
        self.assertIn("RUNNING blocks AI use", instruction)
        self.assertIn("never advise starting MO2", instruction)
        self.assertIn("not proof that an inference test ran", instruction)

    def test_provider_rejects_untyped_or_authority_bearing_context(self):
        provider = LocalLlamaCppProvider(Config(), lambda request, timeout: (200, b"{}"))
        with self.assertRaises(ValueError):
            provider.execute("task", trusted_runtime_context={"authority": "allow_all"})

    def test_controller_captures_one_context_snapshot_in_durable_run_record(self):
        class Provider:
            def __init__(self):
                self.context = None

            def execute(self, task, *, correction=None, trusted_runtime_context=None):
                self.context = trusted_runtime_context
                return ProviderResponse(200, (
                    '{"schema_version":2,"status":"PASS","summary":"done",'
                    '"user_response":"Done."}'), "qwen3.8-27b-q4_k_m")

        with tempfile.TemporaryDirectory() as directory:
            provider = Provider()
            expected = reduce_readiness(
                (component(),), observed_at=NOW, local_now=NOW).prompt_context(now=NOW)
            record = Controller(
                Config(run_directory=Path(directory)), provider,
                runtime_context_provider=lambda: expected).run("Hello")
            self.assertEqual(provider.context, expected)
            self.assertEqual(record["schema_version"], 2)
            self.assertEqual(record["trusted_runtime_context"], expected)
            self.assertEqual(record["trusted_runtime_context_status"], "available")


class ProjectionAndLifecycleTests(unittest.TestCase):
    def test_readiness_is_projected_and_transition_is_a_bounded_ui_event(self):
        provider = VisualizerStateProvider()
        observer = VisualizerRuntimeObserver(provider)
        readiness = reduce_readiness((component(),), observed_at=NOW, local_now=NOW)
        observer.publish_readiness(readiness)
        snapshot = provider.snapshot()
        self.assertIs(snapshot.readiness.state, ReadinessState.READY)
        self.assertEqual(provider.events()[-1].event_type, EventType.READINESS_CHANGED)

    def test_snapshot_contract_serializes_readiness_without_new_control_surface(self):
        readiness = reduce_readiness((component(),), observed_at=NOW, local_now=NOW)
        source = TrustedRuntimeState(
            SystemState.IDLE, TaskView(), default_compute(), inactive_agents(),
            MemoryView(), ExecutionView(), ReviewView(), readiness=readiness)
        snapshot = project_snapshot(source, snapshot_id="health", generated_at=NOW)
        self.assertIs(snapshot.readiness, readiness)

    def test_runtime_ready_requires_both_health_and_browser_behavior(self):
        provider = VisualizerStateProvider()
        observer = VisualizerRuntimeObserver(provider)
        observer.publish_readiness(reduce_readiness(
            (component(),), observed_at=NOW, local_now=NOW))
        server = VisualizerServer(provider, port=0)
        server.start()
        try:
            ready, reason = probe_http_runtime(
                f"http://127.0.0.1:{server.bound_port}/graci/visualizer/v1/health", 2)
        finally:
            server.stop()
        self.assertTrue(ready)
        self.assertEqual(reason, "loopback_runtime_and_browser_responded")

    def test_lifecycle_ledger_marks_unrecorded_exit_and_retains_terminal_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lifecycle.jsonl"
            ledger = ResidentLifecycleLedger(path, clock=lambda: NOW)
            ledger.begin("a" * 32)
            ledger.append("a" * 32, "resident_heartbeat")
            ledger.begin("b" * 32)
            ledger.append("b" * 32, "resident_stopped")
            records = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
            self.assertIn("previous_resident_exit_unrecorded",
                          [item["event"] for item in records])
            self.assertEqual(records[-1]["event"], "resident_stopped")


if __name__ == "__main__":
    unittest.main()
