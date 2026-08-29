import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from graci.config import Config
from graci.controller import Controller
from graci.provider import LocalLlamaCppProvider, ProviderResponse


class FakeProvider:
    def __init__(self, content: str | list[str], status: int = 200):
        contents = [content] if isinstance(content, str) else content
        self.responses = [ProviderResponse(status, item, "qwen3.8-27b-q4_k_m")
                          for item in contents]
        self.calls = []

    def execute(self, task: str, *, correction: str | None = None) -> ProviderResponse:
        self.calls.append((task, correction))
        return self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Config(run_directory=Path(self.temp.name))

    def execute(self, content: str):
        return Controller(self.config, FakeProvider(content)).run("Return a deterministic result.")

    def persisted(self, record):
        path = Path(self.temp.name) / f"{record['run_id']}.json"
        self.assertTrue(path.is_file())
        return json.loads(path.read_text(encoding="utf-8"))

    def test_valid_structured_response_is_truthful_pass_and_persisted(self):
        record = self.execute('{"schema_version":1,"status":"PASS","summary":"done"}')
        self.assertEqual(record["status"], "PASS")
        saved = self.persisted(record)
        self.assertEqual(saved["validated_model_result"]["summary"], "done")
        self.assertEqual(saved["execution"], {
            "provider": "local-llama-cpp", "node": "3090-primary-localhost",
            "endpoint": "http://127.0.0.1:8080/v1", "model": "qwen3.8-27b-q4_k_m"})
        self.assertEqual(saved["http_status"], 200)
        self.assertIsNotNone(saved["started_at"])
        self.assertIsNotNone(saved["ended_at"])

    def test_v2_separates_user_response_from_internal_summary(self):
        record = self.execute(
            '{"schema_version":2,"status":"PASS","summary":"protocol complete",'
            '"user_response":"Hi, I am GRACI."}')
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["validated_model_result"]["summary"], "protocol complete")
        self.assertEqual(record["validated_model_result"]["user_response"],
                         "Hi, I am GRACI.")

    def test_v2_fail_remains_fail_with_internal_diagnostics(self):
        record = self.execute(
            '{"schema_version":2,"status":"FAIL","summary":"request could not be completed",'
            '"user_response":null}')
        self.assertEqual(record["status"], "FAIL")
        self.assertIn("request could not be completed", record["errors"][0])

    def test_v2_user_response_contract_fails_closed(self):
        samples = (
            '{"schema_version":2,"status":"PASS","summary":"done","user_response":null}',
            '{"schema_version":2,"status":"FAIL","summary":"failed","user_response":"leak"}',
            '{"schema_version":2,"status":"PASS","summary":"done"}',
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(self.execute(sample)["status"], "FAIL")

    def test_valid_model_fail_is_truthful_fail(self):
        record = self.execute('{"schema_version":1,"status":"FAIL","summary":"cannot complete"}')
        self.assertEqual(record["status"], "FAIL")
        self.assertIn("model reported failure", record["errors"][0])
        self.persisted(record)

    def test_malformed_model_response_fails_closed(self):
        record = self.execute("not json")
        self.assertEqual(record["status"], "FAIL")
        self.assertIn("validation_error", record["errors"][0])
        self.assertEqual(len(record["model_generation_attempts"]), 2)
        self.persisted(record)

    def test_observed_fenced_json_retries_once_and_recovers_in_same_run(self):
        fenced = ('```json\n{"schema_version":2,"status":"PASS",'
                  '"summary":"done","user_response":"Hello."}\n```')
        valid = ('{"schema_version":2,"status":"PASS",'
                 '"summary":"done","user_response":"Hello."}')
        provider = FakeProvider([fenced, valid])
        record = Controller(self.config, provider).run("Hello, Gracie.")
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(provider.calls[0], ("Hello, Gracie.", None))
        self.assertEqual(provider.calls[1][0], "Hello, Gracie.")
        self.assertIn("not valid JSON", provider.calls[1][1])
        self.assertEqual([item["outcome"] for item in record["model_generation_attempts"]],
                         ["REJECTED", "VALIDATED"])
        self.assertEqual(record["model_generation_attempts"][0]["content"], fenced)
        self.assertEqual(len(list(Path(self.temp.name).glob("*.json"))), 1)

    def test_retry_exhaustion_preserves_both_attempts_and_fails(self):
        provider = FakeProvider(["", "still not json"])
        record = Controller(self.config, provider).run("same authoritative task")
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual([call[0] for call in provider.calls],
                         ["same authoritative task", "same authoritative task"])
        self.assertTrue(all(item["outcome"] == "REJECTED"
                            for item in record["model_generation_attempts"]))
        self.assertIsNone(record["validated_model_result"])
        self.assertEqual(len(list(Path(self.temp.name).glob("*.json"))), 1)

    def test_missing_and_invalid_required_fields_fail_closed(self):
        samples = [
            '{"schema_version":1,"status":"PASS"}',
            '{"schema_version":"1","status":"PASS","summary":"done"}',
            '{"schema_version":1,"status":"OK","summary":"done"}',
            '{"schema_version":1,"status":"PASS","summary":""}',
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(self.execute(sample)["status"], "FAIL")

    def test_http_failure_is_persisted(self):
        def failing_transport(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 503, "Unavailable", {}, None)

        provider = LocalLlamaCppProvider(self.config, failing_transport)
        record = Controller(self.config, provider).run("test HTTP failure")
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["http_status"], 503)
        self.assertIn("provider_error", record["errors"][0])
        self.persisted(record)

    def test_http_200_with_invalid_envelope_is_not_pass(self):
        provider = LocalLlamaCppProvider(self.config, lambda request, timeout: (200, b'{}'))
        record = Controller(self.config, provider).run("test invalid envelope")
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["http_status"], 200)
        self.persisted(record)

    def test_governed_request_uses_native_strict_json_schema(self):
        captured = {}

        def transport(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return 200, json.dumps({
                "model": "qwen3.8-27b-q4_k_m",
                "choices": [{"message": {"content": (
                    '{"schema_version":2,"status":"PASS","summary":"done",'
                    '"user_response":"Hello."}')}}],
            }).encode("utf-8")

        record = Controller(self.config, LocalLlamaCppProvider(
            self.config, transport)).run("Hello, Gracie.")
        response_format = captured["body"]["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertTrue(response_format["json_schema"]["strict"])
        self.assertEqual(len(response_format["json_schema"]["schema"]["oneOf"]), 2)
        self.assertEqual(record["status"], "PASS")

    def test_corrective_request_keeps_qwen_compatible_single_system_message(self):
        captured = {}

        def transport(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return 200, json.dumps({
                "model": "qwen3.8-27b-q4_k_m",
                "choices": [{"message": {"content": (
                    '{"schema_version":2,"status":"PASS","summary":"done",'
                    '"user_response":"Hello."}')}}],
            }).encode("utf-8")

        LocalLlamaCppProvider(self.config, transport).execute(
            "Hello, Gracie.", correction="model output is not valid JSON: Expecting value")
        messages = captured["body"]["messages"]
        self.assertEqual([item["role"] for item in messages], ["system", "user"])
        self.assertIn("preceding generation attempt was rejected", messages[0]["content"])

    def test_response_model_mismatch_fails_closed(self):
        provider = FakeProvider('{"schema_version":1,"status":"PASS","summary":"done"}')
        provider.responses[0] = ProviderResponse(200, provider.responses[0].content, "other-model")
        record = Controller(self.config, provider).run("test model mismatch")
        self.assertEqual(record["status"], "FAIL")
        self.assertIn("provider response model", record["errors"][0])
        self.assertEqual(len(provider.calls), 1)
        self.persisted(record)

    def test_nonlocal_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            Config(endpoint="http://192.168.0.101:8080/v1")
        with self.assertRaises(ValueError):
            Config(endpoint="https://api.example.com/v1")
        with self.assertRaises(ValueError):
            Config(endpoint="http://user:secret@127.0.0.1:8080/v1")
        with self.assertRaises(ValueError):
            Config(node="4090-optional")


if __name__ == "__main__":
    unittest.main()
