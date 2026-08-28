import json
import urllib.error
import unittest
from dataclasses import replace
from pathlib import Path

from graci.availability import (
    MO2_PROCESS_NAME, MO2_STATUS_URL, Mo2State, Mo2StatusResult,
    Phase3CEligibilityReason, check_4090_mo2_status, evaluate_4090_eligibility,
)
from graci.registry import (
    GLM_MODEL_ID, OPTIONAL_ENDPOINT_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID,
    HealthState, build_phase3a_registry,
)
from graci.routing import Phase3BRoleRouter


def response(state, reason, *, process_name=MO2_PROCESS_NAME):
    return json.dumps({"schema_version": 1, "process_name": process_name,
                       "state": state, "reason_code": reason}).encode()


def status(state):
    reasons = {Mo2State.RUNNING: "exact_process_found",
               Mo2State.NOT_RUNNING: "exact_process_absent",
               Mo2State.UNKNOWN: "malformed_response",
               Mo2State.ERROR: "query_timeout"}
    return Mo2StatusResult(state, reasons[state], "2026-01-01T00:00:00Z", 200)


def registry_with(*, health=HealthState.HEALTHY,
                  models=(QWEN_MODEL_ID, GLM_MODEL_ID)):
    registry = build_phase3a_registry()
    for endpoint_id in (PRIMARY_ENDPOINT_ID, OPTIONAL_ENDPOINT_ID):
        endpoint = replace(registry.endpoints[endpoint_id], health_state=health,
                           health_reason="test_fixture", observed_models=models)
        registry = registry.with_endpoint(endpoint)
    return registry


class Mo2DetectorTests(unittest.TestCase):
    def test_exact_process_found_and_absent(self):
        for remote_state, reason, expected in (
            ("RUNNING", "exact_process_found", Mo2State.RUNNING),
            ("NOT_RUNNING", "exact_process_absent", Mo2State.NOT_RUNNING),
        ):
            with self.subTest(remote_state=remote_state):
                result = check_4090_mo2_status(
                    transport=lambda request, timeout, s=remote_state, r=reason:
                    (200, response(s, r)))
                self.assertEqual(result.state, expected)

    def test_timeout_authentication_and_network_errors_fail_closed(self):
        def auth(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 401, "denied", {}, None)
        cases = [
            (lambda request, timeout: (_ for _ in ()).throw(TimeoutError()), "query_timeout"),
            (auth, "authentication_failure"),
            (lambda request, timeout: (_ for _ in ()).throw(
                urllib.error.URLError("offline")), "query_failure:URLError"),
        ]
        for transport, reason in cases:
            with self.subTest(reason=reason):
                result = check_4090_mo2_status(transport=transport)
                self.assertEqual(result.state, Mo2State.ERROR)
                self.assertEqual(result.reason_code, reason)

    def test_malformed_similar_case_and_empty_semantics(self):
        malformed = [
            b"not-json",
            response("RUNNING", "exact_process_found", process_name="ModOrganizer2.exe"),
            response("RUNNING", "exact_process_found", process_name="modorganizer.exe"),
            response("NOT_RUNNING", "exact_process_found"),
            json.dumps({"schema_version": 1, "process_name": MO2_PROCESS_NAME,
                        "state": "NOT_RUNNING", "reason_code": "exact_process_absent",
                        "extra": True}).encode(),
            b"",
        ]
        for raw in malformed:
            with self.subTest(raw=raw):
                self.assertEqual(check_4090_mo2_status(
                    transport=lambda request, timeout, body=raw: (200, body)).state,
                    Mo2State.UNKNOWN)
        self.assertEqual(check_4090_mo2_status(
            transport=lambda request, timeout: (200, response(
                "NOT_RUNNING", "exact_process_absent"))).state, Mo2State.NOT_RUNNING)

    def test_windows_case_semantics_are_server_normalized_but_contract_is_exact(self):
        result = check_4090_mo2_status(transport=lambda request, timeout: (
            200, response("RUNNING", "exact_process_found")))
        self.assertEqual(result.state, Mo2State.RUNNING)
        self.assertEqual(MO2_PROCESS_NAME, "ModOrganizer.exe")

    def test_fixed_get_only_non_inference_request(self):
        seen = {}
        def transport(request, timeout):
            seen.update(url=request.full_url, method=request.method, data=request.data,
                        timeout=timeout)
            return 200, response("NOT_RUNNING", "exact_process_absent")
        check_4090_mo2_status(timeout_seconds=2.5, transport=transport)
        self.assertEqual(seen, {"url": MO2_STATUS_URL, "method": "GET",
                                "data": None, "timeout": 2.5})
        self.assertNotIn("chat/completions", seen["url"])

    def test_endpoint_reference_is_exact_read_only_and_non_inference(self):
        script = (Path(__file__).resolve().parents[1] / "phase3c" / "windows" /
                  "mo2-status.ps1").read_text(encoding="utf-8")
        self.assertIn("-Filter \"Name = 'ModOrganizer.exe'\"", script)
        self.assertIn("OrdinalIgnoreCase", script)
        self.assertIn("$context.Request.HttpMethod -cne 'GET'", script)
        for prohibited in ("Stop-Process", "Invoke-Command", "Enable-PSRemoting",
                           "chat/completions"):
            self.assertNotIn(prohibited, script)


class EligibilityTests(unittest.TestCase):
    def test_eligible_only_when_all_signals_pass(self):
        result = evaluate_4090_eligibility(
            registry_with(), QWEN_MODEL_ID, status(Mo2State.NOT_RUNNING))
        self.assertTrue(result.eligible)
        self.assertEqual(result.reason_code, Phase3CEligibilityReason.ELIGIBLE)

    def test_reason_precedence_and_fail_closed_states(self):
        healthy = registry_with()
        cases = [
            (healthy, status(Mo2State.RUNNING), QWEN_MODEL_ID, {},
             Phase3CEligibilityReason.MO2_RUNNING),
            (healthy, status(Mo2State.UNKNOWN), QWEN_MODEL_ID, {},
             Phase3CEligibilityReason.MO2_STATE_UNKNOWN),
            (healthy, status(Mo2State.ERROR), QWEN_MODEL_ID, {},
             Phase3CEligibilityReason.MO2_QUERY_ERROR),
            (registry_with(health=HealthState.UNKNOWN), status(Mo2State.NOT_RUNNING),
             QWEN_MODEL_ID, {}, Phase3CEligibilityReason.ENDPOINT_UNKNOWN),
            (registry_with(health=HealthState.UNHEALTHY), status(Mo2State.NOT_RUNNING),
             QWEN_MODEL_ID, {}, Phase3CEligibilityReason.ENDPOINT_UNHEALTHY),
            (registry_with(models=(GLM_MODEL_ID,)), status(Mo2State.NOT_RUNNING),
             QWEN_MODEL_ID, {}, Phase3CEligibilityReason.REQUIRED_MODEL_UNAVAILABLE),
            (healthy, status(Mo2State.NOT_RUNNING), "missing", {},
             Phase3CEligibilityReason.REQUIRED_MODEL_UNAVAILABLE),
            (healthy, status(Mo2State.NOT_RUNNING), QWEN_MODEL_ID,
             {"applicable_policy_checks_pass": False}, Phase3CEligibilityReason.POLICY_BLOCKED),
        ]
        for registry, mo2, model, kwargs, expected in cases:
            with self.subTest(expected=expected):
                result = evaluate_4090_eligibility(registry, model, mo2, **kwargs)
                self.assertFalse(result.eligible)
                self.assertEqual(result.reason_code, expected)

    def test_disabled_node_precedes_other_failures(self):
        registry = registry_with(health=HealthState.UNHEALTHY)
        nodes = dict(registry.nodes)
        nodes["4090"] = replace(nodes["4090"], enabled=False)
        result = evaluate_4090_eligibility(replace(registry, nodes=nodes), QWEN_MODEL_ID,
                                           status(Mo2State.RUNNING))
        self.assertEqual(result.reason_code, Phase3CEligibilityReason.NODE_DISABLED)

    def test_mo2_running_and_unknown_override_endpoint_health(self):
        for mo2 in (Mo2State.RUNNING, Mo2State.UNKNOWN, Mo2State.ERROR):
            for health in (HealthState.HEALTHY, HealthState.UNHEALTHY):
                with self.subTest(mo2=mo2, health=health):
                    result = evaluate_4090_eligibility(
                        registry_with(health=health), QWEN_MODEL_ID, status(mo2))
                    self.assertFalse(result.eligible)
                    self.assertIn(result.reason_code, {
                        Phase3CEligibilityReason.MO2_RUNNING,
                        Phase3CEligibilityReason.MO2_STATE_UNKNOWN,
                        Phase3CEligibilityReason.MO2_QUERY_ERROR})

    def test_primary_role_routing_is_independent(self):
        registry = registry_with()
        before = Phase3BRoleRouter(registry).resolve("implementer")
        for state in (Mo2State.RUNNING, Mo2State.UNKNOWN, Mo2State.ERROR):
            evaluate_4090_eligibility(registry, QWEN_MODEL_ID, status(state))
            after = Phase3BRoleRouter(registry).resolve("implementer")
            self.assertEqual(after, before)
            self.assertEqual(after.node_id, "3090")


if __name__ == "__main__":
    unittest.main()
