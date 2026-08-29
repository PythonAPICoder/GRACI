"""Regression coverage for QA-006 GRACI acronym truthfulness."""

import json
import unittest

from graci.config import Config
from graci.controller import Controller
from graci.provider import LocalLlamaCppProvider


CANONICAL_EXPANSION = "General Reasoning And Conversational Intelligence"


class QA006Transport:
    def __init__(self):
        self.bodies = []

    def __call__(self, request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        self.bodies.append(body)
        task = body["messages"][1]["content"]
        if "stand for" in task.lower() or "expand" in task.lower():
            user_response = f"GRACI stands for {CANONICAL_EXPANSION}."
        else:
            user_response = "I'm GRACI, your local assistant."
        content = json.dumps({
            "schema_version": 2,
            "status": "PASS",
            "summary": "identity question answered",
            "user_response": user_response,
        })
        envelope = {
            "model": "qwen3.8-27b-q4_k_m",
            "choices": [{"message": {"content": content}}],
        }
        return 200, json.dumps(envelope).encode("utf-8")


class QA006AcronymTests(unittest.TestCase):
    def setUp(self):
        self.transport = QA006Transport()
        self.provider = LocalLlamaCppProvider(Config(), self.transport)

    def run_question(self, question):
        return Controller(Config(), self.provider).run(question)

    def test_identity_contract_contains_only_the_canonical_expansion(self):
        self.provider.execute("What does GRACI stand for?")
        instruction = self.transport.bodies[-1]["messages"][0]["content"]
        self.assertIn(f"G.R.A.C.I. stands for {CANONICAL_EXPANSION}.", instruction)
        self.assertIn("Use that exact expansion", instruction)
        self.assertIn("equivalent acronym question", instruction)
        self.assertIn("never invent or substitute another expansion", instruction)
        self.assertEqual(instruction.count(CANONICAL_EXPANSION), 1)

    def test_graci_and_dotted_questions_return_exact_canonical_wording(self):
        for question in (
                "What does GRACI stand for?",
                "What does G.R.A.C.I. stand for?",
                "Can you expand the name GRACI?",
        ):
            with self.subTest(question=question):
                record = self.run_question(question)
                result = record["validated_model_result"]
                self.assertEqual(result["schema_version"], 2)
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(
                    result["user_response"],
                    f"GRACI stands for {CANONICAL_EXPANSION}.",
                )
                self.assertNotIn("Generative", result["user_response"])
                self.assertNotIn("Artificial", result["user_response"])
                self.assertNotIn("Automation", result["user_response"])
                self.assertNotIn("Coordination", result["user_response"])

    def test_normal_identity_remains_graci_without_protocol_leakage(self):
        record = self.run_question("Hi Gracie, who are you?")
        result = record["validated_model_result"]
        self.assertEqual(result["user_response"], "I'm GRACI, your local assistant.")
        self.assertNotIn("schema", result["user_response"])
        self.assertNotIn("qwen", result["user_response"].lower())
        self.assertNotIn("identity question answered", result["user_response"])


if __name__ == "__main__":
    unittest.main()
