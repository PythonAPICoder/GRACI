import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from graci.phase3b import Phase3BController
from graci.provider import LocalLlamaCppProvider, ProviderError, ProviderResponse
from graci.registry import (GLM_MODEL_ID, OPTIONAL_ENDPOINT_ID, OPTIONAL_NODE_ID,
                            PRIMARY_BASE_URL, PRIMARY_ENDPOINT_ID, PRIMARY_NODE_ID,
                            QWEN_MODEL_ID, HealthState, ModelRole,
                            build_phase3a_registry, evaluate_eligibility)
from graci.review import adjudicate, validate_review
from graci.routing import Phase3BRoleRouter, RoleResolutionError
from graci.validation import ValidationError


def healthy_registry():
    registry = build_phase3a_registry()
    endpoint = replace(registry.endpoints[PRIMARY_ENDPOINT_ID],
                       health_state=HealthState.HEALTHY,
                       health_reason="test_fixture",
                       observed_models=(QWEN_MODEL_ID, GLM_MODEL_ID))
    return registry.with_endpoint(endpoint)


class SequenceImplementer:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def propose_repair_decision(self, task, context):
        self.calls += 1
        return ProviderResponse(200, json.dumps(next(self.responses)), QWEN_MODEL_ID)


class FakeReviewer:
    def __init__(self, content=None, *, model=GLM_MODEL_ID, error=None):
        self.content, self.model, self.error = content, model, error
        self.calls, self.context = 0, None

    def review(self, context):
        self.calls += 1
        self.context = context
        if self.error:
            raise self.error
        return ProviderResponse(200, self.content, self.model)


def review(verdict="PASS", rationale="Implementation matches deterministic evidence."):
    return json.dumps({"schema_version": 1, "verdict": verdict, "findings": [],
                       "rationale": rationale})


class RoleRoutingTests(unittest.TestCase):
    def test_roles_resolve_exact_primary_models(self):
        router = Phase3BRoleRouter(healthy_registry())
        implementer = router.resolve("implementer")
        reviewer = router.resolve("reviewer")
        verifier = router.resolve("verifier")
        self.assertEqual((implementer.node_id, implementer.endpoint, implementer.model),
                         (PRIMARY_NODE_ID, PRIMARY_BASE_URL, QWEN_MODEL_ID))
        self.assertEqual((reviewer.node_id, reviewer.endpoint, reviewer.model),
                         (PRIMARY_NODE_ID, PRIMARY_BASE_URL, GLM_MODEL_ID))
        self.assertEqual(verifier.model, GLM_MODEL_ID)

    def test_unsupported_missing_unhealthy_and_disabled_fail_closed(self):
        with self.assertRaises(RoleResolutionError):
            Phase3BRoleRouter(healthy_registry()).resolve("general_reasoning")
        registry = healthy_registry()
        cases = [
            replace(registry, models={QWEN_MODEL_ID: registry.models[QWEN_MODEL_ID]}),
            registry.with_endpoint(replace(registry.endpoints[PRIMARY_ENDPOINT_ID],
                                           health_state=HealthState.UNKNOWN)),
            replace(registry, nodes={**registry.nodes, PRIMARY_NODE_ID:
                                     replace(registry.nodes[PRIMARY_NODE_ID], enabled=False)}),
        ]
        for candidate in cases:
            with self.subTest(candidate=candidate):
                with self.assertRaises(RoleResolutionError):
                    Phase3BRoleRouter(candidate).resolve("reviewer" if len(candidate.models) == 1 else "implementer")

    def test_4090_is_blocked_even_when_healthy(self):
        registry = healthy_registry()
        remote = replace(registry.endpoints[OPTIONAL_ENDPOINT_ID],
                         health_state=HealthState.HEALTHY,
                         observed_models=(QWEN_MODEL_ID, GLM_MODEL_ID))
        registry = registry.with_endpoint(remote)
        result = evaluate_eligibility(registry, OPTIONAL_NODE_ID, OPTIONAL_ENDPOINT_ID,
                                      GLM_MODEL_ID, required_role=ModelRole.REVIEWER,
                                      policy_state="phase3b")
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason_code.value, "policy_blocked_node")

    def test_provider_uses_exact_binding_and_rejects_identity_mismatch(self):
        binding = Phase3BRoleRouter(healthy_registry()).resolve("reviewer")
        seen = {}
        def transport(request, timeout):
            seen["url"] = request.full_url
            seen["body"] = json.loads(request.data)
            return 200, json.dumps({"model": "wrong", "choices": [{"message": {
                "content": review()}}]}).encode()
        config = Phase3BController._config(binding, Path("runs"))
        response = LocalLlamaCppProvider(config, transport=transport).review({"bounded": True})
        self.assertEqual(seen["url"], PRIMARY_BASE_URL + "/chat/completions")
        self.assertEqual(seen["body"]["model"], GLM_MODEL_ID)
        self.assertEqual(response.response_model, "wrong")
        with self.assertRaises(ValidationError):
            if response.response_model != binding.model:
                raise ValidationError("identity mismatch")


class Phase3BWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "tests").mkdir()
        (self.root / "value.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.root / "tests" / "test_value.py").write_text(
            "import unittest\nfrom value import VALUE\nclass T(unittest.TestCase):\n"
            " def test_value(self): self.assertEqual(VALUE, 2)\n", encoding="utf-8")
        self.runs = self.root / "evidence"

    def tearDown(self):
        self.temp.cleanup()

    def controller(self, reviewer, *, implementer=None):
        implementer = implementer or SequenceImplementer([
            {"schema_version": 1, "action": "write_text", "target_path": "value.py",
             "content": "VALUE = 2\n", "rationale": "fix value"},
            {"schema_version": 1, "action": "run_tests", "rationale": "verify"},
        ])
        return Phase3BController(
            self.root, registry=healthy_registry(), readable_files=("value.py", "tests/test_value.py"),
            editable_files=("value.py",), run_directory=self.runs,
            implementer_provider=implementer, reviewer_provider=reviewer)

    def test_reviewer_pass_produces_pass_and_durable_distinct_identity(self):
        reviewer = FakeReviewer(review())
        record = self.controller(reviewer).run("Set VALUE to 2 and verify it.")
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["adjudication"]["result"], "PASS")
        self.assertEqual(record["role_routing"]["implementer"]["model"], QWEN_MODEL_ID)
        self.assertEqual(record["role_routing"]["reviewer"]["model"], GLM_MODEL_ID)
        self.assertTrue(record["review"]["read_only"])
        self.assertNotIn("tools", reviewer.context)
        saved = json.loads((self.runs / f"{record['run_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "PASS")

    def test_reviewer_fail_prevents_pass_and_persists_findings(self):
        finding = {"severity": "high", "message": "obvious defect"}
        reviewer = FakeReviewer(json.dumps({"schema_version": 1, "verdict": "FAIL",
                                            "findings": [finding], "rationale": "defect"}))
        record = self.controller(reviewer).run("Set VALUE to 2.")
        self.assertEqual(record["status"], "REVIEW_REJECTED")
        self.assertEqual(record["review"]["findings"], [finding])
        self.assertEqual(record["deterministic_verification"]["status"], "PASS")

    def test_malformed_provider_failure_and_model_mismatch_fail_closed(self):
        reviewers = [FakeReviewer("```json\n{}\n```"),
                     FakeReviewer(error=ProviderError("offline")),
                     FakeReviewer(review(), model=QWEN_MODEL_ID)]
        for index, reviewer in enumerate(reviewers):
            with self.subTest(index=index):
                (self.root / "value.py").write_text("VALUE = 1\n", encoding="utf-8")
                record = self.controller(reviewer).run("Set VALUE to 2.")
                self.assertEqual(record["status"], "REVIEW_ERROR")
                self.assertEqual(record["review"]["invocation_status"], "ERROR")

    def test_failed_tests_do_not_invoke_reviewer(self):
        reviewer = FakeReviewer(review())
        implementer = SequenceImplementer([
            {"schema_version": 1, "action": "run_tests", "rationale": "verify"},
            {"schema_version": 1, "action": "finish", "rationale": "stop"},
        ])
        record = self.controller(reviewer, implementer=implementer).run("Do impossible task.")
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(reviewer.calls, 0)
        self.assertEqual(record["review"]["invocation_status"], "NOT_INVOKED")

    def test_reviewer_fact_disagreement_does_not_change_test_fact(self):
        reviewer = FakeReviewer(review("PASS", "The tests failed, but I approve."))
        record = self.controller(reviewer).run("Set VALUE to 2.")
        self.assertEqual(record["deterministic_verification"]["status"], "PASS")
        self.assertIn("tests failed", record["review"]["parsed_result"]["rationale"])

    def test_contract_and_adjudication_are_strict(self):
        with self.assertRaises(ValidationError):
            validate_review('{"schema_version":1,"verdict":"MAYBE","findings":[],"rationale":"x"}')
        with self.assertRaises(ValidationError):
            validate_review(json.dumps({"schema_version": 1, "verdict": "PASS", "findings": [],
                                        "rationale": "x" * 4001}))
        self.assertEqual(adjudicate(False, "COMPLETE", "PASS")[0], "FAIL")
        self.assertEqual(adjudicate(True, "COMPLETE", "FAIL")[0], "REVIEW_REJECTED")
        self.assertEqual(adjudicate(True, "ERROR", None)[0], "REVIEW_ERROR")


if __name__ == "__main__":
    unittest.main()
