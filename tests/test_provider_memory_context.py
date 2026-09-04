"""Provider binding tests for bounded untrusted memory context."""

import json
import tempfile
import unittest
from pathlib import Path

from graci.config import Config
from graci.memory_context import (AUTHORITY_DENIALS, MAX_MEMORY_CONTEXT_RECORDS,
                                  validate_memory_context)
from graci.provider import LocalLlamaCppProvider, ProviderResponse


MEMORY_ID = "01020304-0506-4000-8000-010203040506"
GENERATION_ID = "09080706-0504-4000-8000-090807060504"


def valid_context(record_count: int = 1, content: str = "Synthetic context only.") -> dict:
    records = [{
        "memory_id": f"{MEMORY_ID[:7]}{index:01x}-0506-4000-8000-010203040506",
        "personalized_kind": "preference",
        "relevance_key": "user.synthetic.provider",
        "content": content,
    } for index in range(record_count)]
    return {
        "schema_version": 1,
        "classification": "UNTRUSTED_CONTEXT_DATA",
        "authority_permitted": False,
        "memory_generation_id": GENERATION_ID,
        "record_count": len(records),
        "records": records,
        "authority_denied": list(AUTHORITY_DENIALS),
    }


class ProviderMemoryContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Config(run_directory=Path(self.temp.name))
        self.captured: dict = {}

    def transport(self):
        def transport(request, timeout):
            self.captured["body"] = json.loads(request.data.decode("utf-8"))
            payload = {
                "model": "qwen3.8-27b-q4_k_m",
                "choices": [{"message": {"content": (
                    '{"schema_version":2,"status":"PASS","summary":"done",'
                    '"user_response":"Hello."}')}}],
            }
            return 200, json.dumps(payload).encode("utf-8")
        return transport

    def test_memory_context_is_injected_as_inert_system_context(self):
        context = validate_memory_context(valid_context())
        response = LocalLlamaCppProvider(self.config, self.transport()).execute(
            "Hello, Gracie.", untrusted_memory_context=context)
        self.assertEqual(response.http_status, 200)
        messages = self.captured["body"]["messages"]
        self.assertEqual([item["role"] for item in messages], ["system", "user"])
        self.assertIn("UNTRUSTED_CONTEXT_DATA", messages[0]["content"])
        self.assertIn("Synthetic context only.", messages[0]["content"])
        self.assertIn("cannot grant authority", messages[0]["content"])
        self.assertNotIn("Synthetic context only.", messages[1]["content"])

    def test_memory_context_can_coexist_with_correction(self):
        context = validate_memory_context(valid_context())
        LocalLlamaCppProvider(self.config, self.transport()).execute(
            "Hello, Gracie.", correction="model output was rejected",
            untrusted_memory_context=context)
        system_content = self.captured["body"]["messages"][0]["content"]
        self.assertIn("preceding generation attempt was rejected", system_content)
        self.assertIn("UNTRUSTED_CONTEXT_DATA", system_content)

    def test_invalid_memory_context_fails_closed_before_transport(self):
        context = valid_context()
        context["authority_permitted"] = True
        with self.assertRaises(ValueError):
            LocalLlamaCppProvider(self.config, self.transport()).execute(
                "Hello, Gracie.", untrusted_memory_context=context)
        self.assertNotIn("body", self.captured)

    def test_oversized_memory_context_fails_closed_before_transport(self):
        context = valid_context(MAX_MEMORY_CONTEXT_RECORDS, "é" * 1_000)
        with self.assertRaises(ValueError):
            LocalLlamaCppProvider(self.config, self.transport()).execute(
                "Hello, Gracie.", untrusted_memory_context=context)
        self.assertNotIn("body", self.captured)

    def test_none_memory_context_preserves_existing_request_shape(self):
        LocalLlamaCppProvider(self.config, self.transport()).execute("Hello, Gracie.")
        system_content = self.captured["body"]["messages"][0]["content"]
        self.assertNotIn("UNTRUSTED_CONTEXT_DATA", system_content)


if __name__ == "__main__":
    unittest.main()
