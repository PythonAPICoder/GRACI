import json
import urllib.error
import unittest
from dataclasses import replace

from graci.registry import (GLM_MODEL_ID, OPTIONAL_ENDPOINT_ID, OPTIONAL_NODE_ID,
                            PRIMARY_ENDPOINT_ID, PRIMARY_NODE_ID, QWEN_MODEL_ID,
                            EligibilityReason, HealthState, ModelRole,
                            apply_health_result, build_phase3a_registry,
                            check_openai_models_endpoint, evaluate_eligibility)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = build_phase3a_registry()

    def healthy(self, *models):
        endpoint = self.registry.endpoints[PRIMARY_ENDPOINT_ID]
        result = check_openai_models_endpoint(
            endpoint, expected_models=tuple(models),
            transport=lambda request, timeout: (200, json.dumps({"data": [
                {"id": model} for model in models]}).encode()))
        return self.registry.with_endpoint(apply_health_result(endpoint, result))

    def test_known_topology_and_roles(self):
        self.assertEqual(set(self.registry.nodes), {PRIMARY_NODE_ID, OPTIONAL_NODE_ID})
        self.assertEqual(set(self.registry.endpoints), {PRIMARY_ENDPOINT_ID, OPTIONAL_ENDPOINT_ID})
        self.assertEqual(set(self.registry.models), {QWEN_MODEL_ID, GLM_MODEL_ID})
        self.assertEqual(self.registry.models[QWEN_MODEL_ID].roles,
                         {ModelRole.IMPLEMENTER, ModelRole.GENERAL_REASONING})
        self.assertEqual(self.registry.models[GLM_MODEL_ID].roles,
                         {ModelRole.REVIEWER, ModelRole.VERIFIER})

    def test_healthy_models_response(self):
        endpoint = self.registry.endpoints[PRIMARY_ENDPOINT_ID]
        result = check_openai_models_endpoint(
            endpoint, expected_models=(QWEN_MODEL_ID,),
            transport=lambda request, timeout: (200, b'{"data":[{"id":"qwen3.8-27b-q4_k_m"}]}'))
        self.assertEqual(result.state, HealthState.HEALTHY)
        self.assertEqual(result.observed_models, (QWEN_MODEL_ID,))

    def test_health_failures_are_truthful(self):
        endpoint = self.registry.endpoints[PRIMARY_ENDPOINT_ID]
        cases = [
            (lambda request, timeout: (503, b'{}'), "unexpected_http_status:503"),
            (lambda request, timeout: (_ for _ in ()).throw(TimeoutError()), "request_failure:TimeoutError"),
            (lambda request, timeout: (200, b'not-json'), "malformed_json"),
            (lambda request, timeout: (200, b'{}'), "missing_model_list"),
            (lambda request, timeout: (200, b'{"data":[]}'), "expected_models_absent:" + QWEN_MODEL_ID),
        ]
        for transport, reason in cases:
            with self.subTest(reason=reason):
                result = check_openai_models_endpoint(endpoint, expected_models=(QWEN_MODEL_ID,),
                                                      transport=transport)
                self.assertEqual(result.state, HealthState.UNHEALTHY)
                self.assertEqual(result.reason, reason)

    def test_http_error_is_unhealthy(self):
        endpoint = self.registry.endpoints[PRIMARY_ENDPOINT_ID]
        def fail(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 500, "fail", {}, None)
        self.assertEqual(check_openai_models_endpoint(endpoint, transport=fail).reason,
                         "http_error:500")

    def test_primary_eligibility_and_fail_closed_states(self):
        healthy = self.healthy(QWEN_MODEL_ID)
        result = evaluate_eligibility(healthy, PRIMARY_NODE_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID,
                                      required_role=ModelRole.IMPLEMENTER)
        self.assertTrue(result.eligible)
        self.assertEqual(result.reason_code, EligibilityReason.ELIGIBLE)

        cases = [
            (self.registry, PRIMARY_NODE_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID,
             {}, EligibilityReason.UNKNOWN_HEALTH),
            (self.registry.with_endpoint(replace(self.registry.endpoints[PRIMARY_ENDPOINT_ID],
                                                 health_state=HealthState.UNHEALTHY)),
             PRIMARY_NODE_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID, {},
             EligibilityReason.UNHEALTHY_ENDPOINT),
            (replace(healthy, nodes={**healthy.nodes,
                                    PRIMARY_NODE_ID: replace(healthy.nodes[PRIMARY_NODE_ID], enabled=False)}),
             PRIMARY_NODE_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID, {},
             EligibilityReason.DISABLED_RESOURCE),
            (healthy.with_endpoint(replace(healthy.endpoints[PRIMARY_ENDPOINT_ID], observed_models=())),
             PRIMARY_NODE_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID, {},
             EligibilityReason.MODEL_UNAVAILABLE),
            (healthy, "missing", PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID, {}, EligibilityReason.UNKNOWN_NODE),
            (healthy, PRIMARY_NODE_ID, "missing", QWEN_MODEL_ID, {}, EligibilityReason.UNKNOWN_ENDPOINT),
            (healthy, PRIMARY_NODE_ID, PRIMARY_ENDPOINT_ID, "missing", {}, EligibilityReason.UNKNOWN_MODEL),
            (healthy, PRIMARY_NODE_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID,
             {"required_role": "unknown"}, EligibilityReason.UNKNOWN_ROLE),
            (healthy, PRIMARY_NODE_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID,
             {"policy_state": "future"}, EligibilityReason.UNKNOWN_POLICY_STATE),
        ]
        for registry, node, endpoint, model, kwargs, reason in cases:
            with self.subTest(reason=reason):
                result = evaluate_eligibility(registry, node, endpoint, model, **kwargs)
                self.assertFalse(result.eligible)
                self.assertEqual(result.reason_code, reason)

    def test_malformed_reference_fails_closed(self):
        healthy = self.healthy(QWEN_MODEL_ID)
        result = evaluate_eligibility(healthy, PRIMARY_NODE_ID, OPTIONAL_ENDPOINT_ID, QWEN_MODEL_ID)
        self.assertEqual(result.reason_code, EligibilityReason.MALFORMED_REFERENCE)

    def test_4090_is_always_phase3a_policy_blocked(self):
        endpoint = replace(self.registry.endpoints[OPTIONAL_ENDPOINT_ID],
                           health_state=HealthState.HEALTHY,
                           observed_models=(QWEN_MODEL_ID, GLM_MODEL_ID))
        registry = self.registry.with_endpoint(endpoint)
        result = evaluate_eligibility(registry, OPTIONAL_NODE_ID, OPTIONAL_ENDPOINT_ID, QWEN_MODEL_ID)
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason_code, EligibilityReason.POLICY_BLOCKED_NODE)


if __name__ == "__main__":
    unittest.main()
