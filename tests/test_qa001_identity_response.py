"""Regression coverage for QA-001 GRACI identity and response separation."""

import json
import unittest

from graci.config import Config
from graci.operator_cli import GovernedSummaryResponseConstructor
from graci.provider import LocalLlamaCppProvider
from graci.speech import TranscriptionResult, TranscriptionStatus
from graci.turn_coordinator import ExplicitTurnCoordinator


class CapturingTransport:
    def __init__(self):
        self.body = None

    def __call__(self, request, timeout):
        self.body = json.loads(request.data.decode("utf-8"))
        envelope = {
            "model": "qwen3.8-27b-q4_k_m",
            "choices": [{"message": {"content": json.dumps({
                "schema_version": 2,
                "status": "PASS",
                "summary": "ordinary conversation completed under the governed contract",
                "user_response": "Hi! I'm GRACI, your local assistant.",
            })}}],
        }
        return 200, json.dumps(envelope).encode("utf-8")


class Runtime:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, task):
        self.calls.append(task)
        return self.result


class PushToTalk:
    def begin(self):
        pass

    def end_and_transcribe(self):
        return TranscriptionResult(
            TranscriptionStatus.SUCCESS, "local-stt", 0.1,
            text="Hi GRACI, tell me about yourself.")


class QA001IdentityResponseTests(unittest.TestCase):
    def test_model_boundary_establishes_graci_identity_and_truthful_disclosure(self):
        transport = CapturingTransport()
        provider = LocalLlamaCppProvider(Config(), transport)
        provider.execute("Hi GRACI, tell me about yourself.")
        instruction = transport.body["messages"][0]["content"]
        self.assertIn("acting on behalf of GRACI", instruction)
        self.assertIn("pronounced GRAY-see", instruction)
        self.assertIn("GRACI or Gracie", instruction)
        self.assertIn("explicitly asks", instruction)
        self.assertIn("answer truthfully", instruction)
        self.assertEqual(transport.body["messages"][1]["content"],
                         "Hi GRACI, tell me about yourself.")

    def test_clean_user_response_wins_over_internal_protocol_summary(self):
        result = {
            "status": "PASS",
            "validated_model_result": {
                "schema_version": 2,
                "status": "PASS",
                "summary": "INTERNAL JSON schema validation and protocol status PASS",
                "user_response": "Hi! I'm GRACI, your local assistant.",
            },
            "errors": [],
        }
        response = GovernedSummaryResponseConstructor().construct(result)
        self.assertEqual(response.text, "Hi! I'm GRACI, your local assistant.")
        self.assertNotIn("schema", response.text)
        self.assertNotIn("PASS", response.text)
        legacy = {
            "status": "PASS",
            "validated_model_result": {
                "schema_version": 1, "status": "PASS",
                "summary": "legacy internal summary",
            },
        }
        self.assertIsNone(GovernedSummaryResponseConstructor().construct(legacy))

    def test_explicit_architecture_disclosure_uses_user_response_contract(self):
        governed = {
            "status": "PASS",
            "validated_model_result": {
                "schema_version": 2, "status": "PASS",
                "summary": "architecture question answered",
                "user_response": (
                    "I'm GRACI; my local reasoning stack currently uses Qwen as an "
                    "underlying implementation component."),
            },
        }
        response = GovernedSummaryResponseConstructor().construct(governed)
        self.assertIn("GRACI", response.text)
        self.assertIn("Qwen", response.text)

    def test_typed_and_speech_share_response_contract_and_submit_once_each(self):
        governed = {
            "status": "PASS",
            "validated_model_result": {
                "schema_version": 2, "status": "PASS",
                "summary": "internal diagnostic",
                "user_response": "Hi! I'm GRACI.",
            },
            "errors": [],
        }
        runtime = Runtime(governed)
        coordinator = ExplicitTurnCoordinator(
            runtime, push_to_talk=PushToTalk(),
            final_response_constructor=GovernedSummaryResponseConstructor())
        typed = coordinator.run_typed("Hi GRACI, tell me about yourself.")
        self.assertIsNone(coordinator.begin_speech_turn())
        speech = coordinator.finish_speech_turn()
        self.assertEqual(typed.authoritative_response, speech.authoritative_response)
        self.assertEqual(runtime.calls, ["Hi GRACI, tell me about yourself."] * 2)

    def test_governed_fail_has_diagnostics_but_no_user_facing_response(self):
        governed = {
            "status": "FAIL",
            "validated_model_result": {
                "schema_version": 2, "status": "FAIL",
                "summary": "internal governed failure detail",
                "user_response": None,
            },
            "errors": ["model reported failure: internal governed failure detail"],
        }
        runtime = Runtime(governed)
        turn = ExplicitTurnCoordinator(
            runtime, final_response_constructor=GovernedSummaryResponseConstructor()
        ).run_typed("bounded governed task")
        self.assertEqual(turn.disposition.value, "governed_fail")
        self.assertIsNone(turn.authoritative_response)
        self.assertIn("internal governed failure detail", turn.governed_result["errors"][0])
        self.assertEqual(runtime.calls, ["bounded governed task"])


if __name__ == "__main__":
    unittest.main()
