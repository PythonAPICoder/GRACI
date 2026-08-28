import json
import tempfile
import unittest
import urllib.error
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from graci.availability import Mo2State, Mo2StatusResult
from graci.distributed import DistributedRoutingError, Phase3DDistributedRouter
from graci.registry import (GLM_MODEL_ID, OPTIONAL_ENDPOINT_ID, PRIMARY_ENDPOINT_ID,
                            QWEN_MODEL_ID, HealthResult, HealthState,
                            build_phase3a_registry)


NOW = datetime(2026, 8, 28, tzinfo=timezone.utc)
STAMP = "2026-08-28T00:00:00Z"


def registry(remote_models=(QWEN_MODEL_ID, GLM_MODEL_ID)):
    value = build_phase3a_registry()
    primary = replace(value.endpoints[PRIMARY_ENDPOINT_ID], health_state=HealthState.HEALTHY,
                      health_reason="fixture", observed_models=(QWEN_MODEL_ID, GLM_MODEL_ID))
    remote = replace(value.endpoints[OPTIONAL_ENDPOINT_ID],
                     health_state=HealthState.HEALTHY, health_reason="fixture",
                     observed_models=remote_models)
    return value.with_endpoint(primary).with_endpoint(remote)


def mo2(state=Mo2State.NOT_RUNNING, checked_at=STAMP):
    reason = {Mo2State.NOT_RUNNING: "exact_process_absent",
              Mo2State.RUNNING: "exact_process_found",
              Mo2State.UNKNOWN: "malformed_response",
              Mo2State.ERROR: "query_timeout"}[state]
    return Mo2StatusResult(state, reason, checked_at, 200)


def health(state=HealthState.HEALTHY, models=(QWEN_MODEL_ID, GLM_MODEL_ID),
           checked_at=STAMP):
    return HealthResult(state, "fixture", checked_at, models, 200)


def envelope(model):
    return 200, json.dumps({"model": model, "choices": [{"message": {
        "content": "bounded response"}}]}).encode()


class DistributedRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def router(self, *, mo2_result=None, health_result=None, transport=None,
               value=None, clock=lambda: NOW, max_age=10):
        def default_transport(request, timeout):
            self.calls.append(request.full_url)
            body = json.loads(request.data)
            return envelope(body["model"])
        return Phase3DDistributedRouter(
            value or registry(), run_directory=Path(self.temp.name),
            mo2_check=lambda: mo2_result or mo2(),
            health_check=lambda endpoint, models: health_result or health(),
            inference_transport=transport or default_transport, clock=clock,
            max_eligibility_age_seconds=max_age)

    def test_eligible_explicit_request_routes_to_4090(self):
        result = self.router().route("implementer", "test", prefer_optional=True)
        self.assertEqual(result.node_id, "4090")
        self.assertEqual(self.calls, ["http://192.168.0.101:8080/v1/chat/completions"])
        self.assertTrue(result.evidence["contacted_4090_chat_completions"])
        self.assertFalse(result.evidence["fallback_occurred"])

    def test_default_is_primary_without_optional_gate_contact(self):
        invoked = []
        router = Phase3DDistributedRouter(
            registry(), run_directory=Path(self.temp.name),
            mo2_check=lambda: invoked.append(True),
            health_check=lambda endpoint, models: invoked.append(True),
            inference_transport=lambda request, timeout: envelope(QWEN_MODEL_ID), clock=lambda: NOW)
        result = router.route("implementer", "test")
        self.assertEqual(result.node_id, "3090")
        self.assertEqual(invoked, [])
        self.assertIsNone(result.evidence["eligibility"])

    def test_mo2_running_zero_remote_inference_and_primary_fallback(self):
        result = self.router(mo2_result=mo2(Mo2State.RUNNING)).route(
            "implementer", "test", prefer_optional=True)
        self.assertEqual(result.node_id, "3090")
        self.assertNotIn("192.168.0.101", "".join(self.calls))
        self.assertEqual(result.evidence["fallback_reason"], "mo2_running")

    def test_unknown_and_error_fail_closed_without_remote_inference(self):
        for state in (Mo2State.UNKNOWN, Mo2State.ERROR):
            with self.subTest(state=state):
                self.calls.clear()
                result = self.router(mo2_result=mo2(state)).route(
                    "reviewer", "test", prefer_optional=True)
                self.assertEqual(result.node_id, "3090")
                self.assertNotIn("192.168.0.101", "".join(self.calls))

    def test_unhealthy_or_unreachable_health_falls_back(self):
        result = self.router(health_result=health(HealthState.UNHEALTHY, ())).route(
            "implementer", "test", prefer_optional=True)
        self.assertEqual(result.node_id, "3090")
        self.assertEqual(result.evidence["fallback_reason"], "endpoint_unhealthy")

    def test_required_model_absent_falls_back(self):
        result = self.router(health_result=health(models=(GLM_MODEL_ID,))).route(
            "implementer", "test", prefer_optional=True)
        self.assertEqual(result.node_id, "3090")
        self.assertEqual(result.evidence["fallback_reason"], "required_model_unavailable")

    def test_remote_inference_failure_is_truthful_then_one_primary_attempt(self):
        def transport(request, timeout):
            self.calls.append(request.full_url)
            if "192.168.0.101" in request.full_url:
                raise urllib.error.URLError("offline")
            return envelope(QWEN_MODEL_ID)
        result = self.router(transport=transport).route("implementer", "test",
                                                        prefer_optional=True)
        self.assertEqual(result.node_id, "3090")
        self.assertEqual(len(result.evidence["attempts"]), 2)
        self.assertEqual(result.evidence["attempts"][0]["status"], "ERROR")
        self.assertEqual(result.evidence["attempts"][1]["status"], "SUCCESS")
        self.assertEqual(result.evidence["fallback_reason"], "4090_inference_failure")

    def test_stale_or_future_eligibility_is_never_trusted(self):
        for stamp in ("2026-08-27T23:59:00Z", "2026-08-28T00:00:01Z", "malformed"):
            with self.subTest(stamp=stamp):
                self.calls.clear()
                result = self.router(mo2_result=mo2(checked_at=stamp)).route(
                    "implementer", "test", prefer_optional=True)
                self.assertEqual(result.node_id, "3090")
                self.assertEqual(result.evidence["fallback_reason"], "stale_eligibility")
                self.assertNotIn("192.168.0.101", "".join(self.calls))

    def test_disabled_4090_preserves_3090_only_operation(self):
        value = registry()
        nodes = dict(value.nodes)
        nodes["4090"] = replace(nodes["4090"], enabled=False)
        result = self.router(value=replace(value, nodes=nodes)).route(
            "reviewer", "test", prefer_optional=True)
        self.assertEqual(result.node_id, "3090")
        self.assertEqual(result.evidence["fallback_reason"], "node_disabled")

    def test_role_model_does_not_change_with_endpoint_placement(self):
        implementer = self.router().route("implementer", "test", prefer_optional=True)
        reviewer = self.router().route("reviewer", "test", prefer_optional=True)
        self.assertEqual(implementer.evidence["selected_model"], QWEN_MODEL_ID)
        self.assertEqual(reviewer.evidence["selected_model"], GLM_MODEL_ID)

    def test_server_model_identity_mismatch_falls_back_truthfully(self):
        def transport(request, timeout):
            self.calls.append(request.full_url)
            requested = json.loads(request.data)["model"]
            if "192.168.0.101" in request.full_url:
                return envelope(GLM_MODEL_ID)
            return envelope(requested)
        result = self.router(transport=transport).route("implementer", "test",
                                                        prefer_optional=True)
        self.assertEqual(result.node_id, "3090")
        self.assertEqual(result.evidence["attempts"][0]["status"], "ERROR")
        self.assertIn("identity mismatch", result.evidence["attempts"][0]["error"])
        self.assertEqual(result.evidence["actual_server_model"], QWEN_MODEL_ID)

    def test_both_fail_has_two_attempts_and_no_false_success(self):
        def fail(request, timeout):
            self.calls.append(request.full_url)
            raise OSError("down")
        with self.assertRaises(DistributedRoutingError) as caught:
            self.router(transport=fail).route("implementer", "test", prefer_optional=True)
        evidence = caught.exception.evidence
        self.assertEqual(evidence["final_outcome"], "FAIL")
        self.assertEqual(len(evidence["attempts"]), 2)
        self.assertTrue(all(item["status"] == "ERROR" for item in evidence["attempts"]))

    def test_evidence_is_atomic_complete_and_matches_returned_record(self):
        result = self.router().route("reviewer", "test", prefer_optional=True)
        files = list(Path(self.temp.name).glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text(encoding="utf-8")), result.evidence)
        self.assertEqual(list(Path(self.temp.name).glob(".*.tmp")), [])
        self.assertFalse(result.evidence["cloud_ai_used"])
        self.assertEqual(result.evidence["actual_server_model"], GLM_MODEL_ID)


if __name__ == "__main__":
    unittest.main()
