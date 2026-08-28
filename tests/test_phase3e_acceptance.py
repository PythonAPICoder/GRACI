"""Integrated Phase 3 resource/model router acceptance and closure regressions."""

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from graci.availability import Mo2State, Mo2StatusResult
from graci.distributed import DistributedRoutingError, Phase3DDistributedRouter
from graci.registry import (
    GLM_MODEL_ID, OPTIONAL_ENDPOINT_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID,
    HealthResult, HealthState, ModelRole, build_phase3a_registry,
)
from graci.review import adjudicate
from graci.routing import Phase3BRoleRouter


NOW = datetime(2026, 8, 28, tzinfo=timezone.utc)
STAMP = "2026-08-28T00:00:00Z"
ROOT = Path(__file__).resolve().parents[1]


def accepted_registry(*, optional_enabled=True):
    registry = build_phase3a_registry()
    nodes = dict(registry.nodes)
    nodes["4090"] = replace(nodes["4090"], enabled=optional_enabled)
    registry = replace(registry, nodes=nodes)
    for endpoint_id in (PRIMARY_ENDPOINT_ID, OPTIONAL_ENDPOINT_ID):
        registry = registry.with_endpoint(replace(
            registry.endpoints[endpoint_id], health_state=HealthState.HEALTHY,
            health_reason="phase3e_fixture",
            observed_models=(QWEN_MODEL_ID, GLM_MODEL_ID)))
    return registry


def mo2(state=Mo2State.NOT_RUNNING, stamp=STAMP):
    reasons = {Mo2State.NOT_RUNNING: "exact_process_absent",
               Mo2State.RUNNING: "exact_process_found",
               Mo2State.UNKNOWN: "malformed_response",
               Mo2State.ERROR: "query_timeout"}
    return Mo2StatusResult(state, reasons[state], stamp, 200)


def health(models=(QWEN_MODEL_ID, GLM_MODEL_ID), stamp=STAMP,
           state=HealthState.HEALTHY):
    return HealthResult(state, "phase3e_fixture", stamp, models, 200)


def envelope(model, content="accepted"):
    return 200, json.dumps({"model": model, "choices": [{"message": {
        "content": content}}]}).encode()


class Phase3EAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.calls = []
        self.gates = []

    def tearDown(self):
        self.temp.cleanup()

    def router(self, *, registry=None, mo2_result=None, health_result=None,
               transport=None):
        def mo2_check():
            self.gates.append("mo2")
            return mo2_result or mo2()

        def health_check(endpoint, models):
            self.gates.append(("models", endpoint.endpoint_id, models))
            return health_result or health()

        def inference(request, timeout):
            self.calls.append(request.full_url)
            return envelope(json.loads(request.data)["model"])

        return Phase3DDistributedRouter(
            registry or accepted_registry(), run_directory=Path(self.temp.name),
            mo2_check=mo2_check, health_check=health_check,
            inference_transport=transport or inference, clock=lambda: NOW)

    def test_registry_topology_roles_and_local_only_operation(self):
        registry = accepted_registry(optional_enabled=False)
        router = Phase3BRoleRouter(registry)
        expected = {ModelRole.IMPLEMENTER: QWEN_MODEL_ID,
                    ModelRole.GENERAL_REASONING: QWEN_MODEL_ID,
                    ModelRole.REVIEWER: GLM_MODEL_ID,
                    ModelRole.VERIFIER: GLM_MODEL_ID}
        for role, model in expected.items():
            with self.subTest(role=role):
                binding = router.resolve(role)
                self.assertEqual((binding.node_id, binding.model), ("3090", model))
        result = self.router(registry=registry).route(
            "general_reasoning", "local acceptance", prefer_optional=True)
        self.assertEqual(result.node_id, "3090")
        self.assertEqual(result.evidence["fallback_reason"], "node_disabled")
        self.assertEqual(result.evidence["contact_counts"]["4090_chat_completions"], 0)

    def test_optional_requires_explicit_request_and_each_request_rechecks(self):
        router = self.router()
        first = router.route("implementer", "default")
        self.assertEqual(first.node_id, "3090")
        self.assertEqual(self.gates, [])
        router.route("implementer", "remote one", prefer_optional=True)
        router.route("implementer", "remote two", prefer_optional=True)
        self.assertEqual(self.gates, ["mo2", ("models", OPTIONAL_ENDPOINT_ID,
                                               (QWEN_MODEL_ID,)),
                                      "mo2", ("models", OPTIONAL_ENDPOINT_ID,
                                               (QWEN_MODEL_ID,))])

    def test_fail_closed_gate_matrix_sends_zero_remote_inference(self):
        cases = [
            (mo2(Mo2State.RUNNING), health(), "mo2_running"),
            (mo2(Mo2State.UNKNOWN), health(), "mo2_state_unknown"),
            (mo2(Mo2State.ERROR), health(), "mo2_query_error"),
            (mo2(), health(state=HealthState.UNHEALTHY), "endpoint_unhealthy"),
            (mo2(), health(models=(GLM_MODEL_ID,)), "required_model_unavailable"),
            (mo2(stamp="2026-08-27T23:59:00Z"), health(), "stale_eligibility"),
            (mo2(stamp="2026-08-28T00:00:01Z"), health(), "stale_eligibility"),
        ]
        for mo2_result, health_result, reason in cases:
            with self.subTest(reason=reason):
                self.calls.clear()
                result = self.router(mo2_result=mo2_result,
                                     health_result=health_result).route(
                    "implementer", "fail closed", prefer_optional=True)
                self.assertEqual(result.node_id, "3090")
                self.assertEqual(result.evidence["fallback_reason"], reason)
                self.assertEqual(result.evidence["contact_counts"], {
                    "4090_chat_completions": 0, "3090_chat_completions": 1})

    def test_role_identity_survives_placement_and_mismatch_falls_back(self):
        reviewer = self.router().route("reviewer", "review", prefer_optional=True)
        self.assertEqual((reviewer.node_id, reviewer.evidence["selected_model"]),
                         ("4090", GLM_MODEL_ID))

        def mismatch(request, timeout):
            self.calls.append(request.full_url)
            requested = json.loads(request.data)["model"]
            return envelope(GLM_MODEL_ID if "192.168.0.101" in request.full_url
                            else requested)

        result = self.router(transport=mismatch).route(
            "implementer", "identity", prefer_optional=True)
        self.assertEqual(result.node_id, "3090")
        self.assertEqual(result.evidence["contact_counts"], {
            "4090_chat_completions": 1, "3090_chat_completions": 1})
        self.assertIn("identity mismatch", result.evidence["attempts"][0]["error"])

    def test_bounded_failure_evidence_is_atomic_and_never_false_success(self):
        def fail(request, timeout):
            self.calls.append(request.full_url)
            raise OSError("fixture offline")

        with self.assertRaises(DistributedRoutingError) as caught:
            self.router(transport=fail).route(
                "implementer", "bounded failure", prefer_optional=True)
        record = caught.exception.evidence
        self.assertEqual(record["final_outcome"], "FAIL")
        self.assertEqual(record["contact_counts"], {
            "4090_chat_completions": 1, "3090_chat_completions": 1})
        self.assertEqual(len(record["attempts"]), 2)
        saved = json.loads(next(Path(self.temp.name).glob("*.json")).read_text())
        self.assertEqual(saved, record)
        self.assertEqual(list(Path(self.temp.name).glob(".*.tmp")), [])

    def test_reviewer_adjudication_and_cloud_boundary_remain_deterministic(self):
        self.assertEqual(adjudicate(True, "COMPLETE", "PASS")[0], "PASS")
        self.assertNotEqual(adjudicate(True, "ERROR", None)[0], "PASS")
        self.assertNotEqual(adjudicate(False, "COMPLETE", "PASS")[0], "PASS")
        record = self.router().route("verifier", "verify").evidence
        self.assertFalse(record["cloud_ai_used"])
        self.assertEqual(record["provider"], "local-llama-cpp")
        self.assertNotIn("cloud", record["final_endpoint"])

    def test_phase3_security_surface_has_no_remote_control_or_secrets(self):
        files = [ROOT / "graci" / name for name in
                 ("registry.py", "routing.py", "availability.py", "distributed.py")]
        source = "\n".join(path.read_text(encoding="utf-8") for path in files).lower()
        prohibited = ("stop-process", "invoke-command", "enable-psremoting",
                      "subprocess", "api" + "_key", "authorization:" + " bearer",
                      "openai.com", "anthropic.com")
        for value in prohibited:
            with self.subTest(value=value):
                self.assertNotIn(value, source)

    def test_prior_phase3d_live_evidence_is_valid_and_truthful(self):
        paths = [ROOT / "phase3d" / "evidence" /
                 "1a975f47-55df-4cc5-ad8f-695c6559a78b.json",
                 ROOT / "phase3d" / "evidence" /
                 "5f98916a-700f-4c2f-a7c9-3caa288e5abb.json"]
        eligible, blocked = (json.loads(path.read_text(encoding="utf-8"))
                             for path in paths)
        self.assertEqual((eligible["eligibility"]["mo2"]["state"],
                          eligible["final_node"], eligible["actual_server_model"]),
                         ("NOT_RUNNING", "4090", QWEN_MODEL_ID))
        self.assertEqual((blocked["eligibility"]["mo2"]["state"],
                          blocked["final_node"],
                          blocked["contacted_4090_chat_completions"]),
                         ("RUNNING", "3090", False))


if __name__ == "__main__":
    unittest.main()
