from __future__ import annotations

import ast
import base64
import io
import secrets
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from uuid import uuid4

from phase8f.synthetic_adapter import (
    NOTICE_DELIVER_OPERATION,
    AdapterCode,
    AdapterOutcome,
    SecretMaterial,
    SecretMaterialError,
    SyntheticAdapterRequest,
    SyntheticNoticeAdapter,
    SyntheticNoticeReceipt,
    execute_synthetic_adapter,
)


ROOT = Path(__file__).resolve().parents[1]


class SyntheticAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.destination = "synthetic://notice/focused-test"
        self.resource_id = str(uuid4())
        self.request_id = str(uuid4())
        self.notice_id = str(uuid4())
        self.expected = bytearray(secrets.token_urlsafe(36).encode("ascii"))
        self.expected_snapshot = bytes(self.expected)
        self.adapter = SyntheticNoticeAdapter(
            destination=self.destination,
            resource_id=self.resource_id,
            expected_secret=self.expected,
        )

    def tearDown(self) -> None:
        self.adapter.close()

    def request(self, **changes: object) -> SyntheticAdapterRequest:
        values: dict[str, object] = {
            "request_id": self.request_id,
            "operation": NOTICE_DELIVER_OPERATION,
            "destination": self.destination,
            "resource_id": self.resource_id,
            "payload": {"notice_id": self.notice_id},
        }
        values.update(changes)
        return SyntheticAdapterRequest(**values)  # type: ignore[arg-type]

    def material(self, value: bytes | None = None) -> tuple[SecretMaterial, bytearray]:
        owned = bytearray(self.expected_snapshot if value is None else value)
        return SecretMaterial(owned), owned

    def assert_no_secret(self, secret: bytes, *surfaces: object) -> None:
        text = secret.decode("ascii")
        variants = (
            text,
            secret.hex(),
            base64.b64encode(secret).decode("ascii"),
            base64.urlsafe_b64encode(secret).decode("ascii"),
        )
        rendered = "\n".join(str(surface) for surface in surfaces)
        self.assertFalse(any(variant and variant in rendered for variant in variants))

    def test_exact_notice_delivery_returns_fixed_receipt_and_records_only_ids(self):
        material, owned = self.material()
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            outcome = execute_synthetic_adapter(self.adapter, self.request(), material)

        self.assertEqual(outcome.code, AdapterCode.DELIVERED)
        self.assertEqual(
            outcome.receipt,
            SyntheticNoticeReceipt(self.request_id, self.notice_id),
        )
        self.assertEqual(self.adapter.recorded_calls, (outcome.receipt,))
        self.assertTrue(material.closed)
        self.assertTrue(all(value == 0 for value in owned))
        self.assert_no_secret(
            self.expected_snapshot,
            repr(material), str(material), repr(outcome), str(outcome),
            repr(self.adapter), self.adapter.recorded_calls,
            stdout.getvalue(), stderr.getvalue(),
        )

    def test_wrong_operation_destination_scope_payload_and_secret_fail_closed(self):
        injected = self.expected_snapshot.decode("ascii")
        cases = (
            (self.request(operation=injected), AdapterCode.OPERATION_DENIED, None),
            (self.request(destination=injected), AdapterCode.DESTINATION_DENIED, None),
            (self.request(resource_id=str(uuid4())), AdapterCode.SCOPE_DENIED, None),
            (self.request(payload={"notice_id": self.notice_id, "instruction": injected}),
             AdapterCode.PAYLOAD_DENIED, None),
            (self.request(payload={"notice_id": injected}), AdapterCode.PAYLOAD_DENIED, None),
            (self.request(), AdapterCode.SECRET_DENIED, secrets.token_bytes(32)),
        )
        outcomes: list[AdapterOutcome] = []
        for request, expected_code, replacement in cases:
            material, owned = self.material(replacement)
            outcome = execute_synthetic_adapter(self.adapter, request, material)
            outcomes.append(outcome)
            self.assertEqual(outcome.code, expected_code)
            self.assertIsNone(outcome.receipt)
            self.assertTrue(all(value == 0 for value in owned))
            self.assert_no_secret(self.expected_snapshot, request, outcome)
        self.assertEqual(self.adapter.recorded_calls, ())
        self.assert_no_secret(self.expected_snapshot, outcomes, self.adapter.recorded_calls)

    def test_request_and_secret_representations_never_echo_malicious_fields(self):
        injected = self.expected_snapshot.decode("ascii")
        request = self.request(
            operation=injected,
            destination=injected,
            payload={"notice_id": injected},
        )
        material, _ = self.material()
        self.assert_no_secret(self.expected_snapshot, repr(request), str(request))
        self.assert_no_secret(self.expected_snapshot, repr(material), str(material))

        material.close()
        with self.assertRaises(SecretMaterialError) as caught:
            material._view()
        self.assert_no_secret(self.expected_snapshot, caught.exception)

    def test_adapter_close_erases_expected_material_and_denies_later_calls(self):
        self.adapter.close()
        self.assertTrue(all(value == 0 for value in self.expected))
        material, owned = self.material()
        outcome = execute_synthetic_adapter(self.adapter, self.request(), material)
        self.assertEqual(outcome.code, AdapterCode.ADAPTER_CLOSED)
        self.assertTrue(all(value == 0 for value in owned))
        self.assertEqual(self.adapter.recorded_calls, ())
        self.assert_no_secret(self.expected_snapshot, outcome, self.adapter)

    def test_invalid_configuration_and_material_raise_only_fixed_messages(self):
        injected = self.expected_snapshot.decode("ascii")
        failures: list[Exception] = []
        invalid_destination_secret = bytearray(self.expected_snapshot)
        invalid_resource_secret = bytearray(self.expected_snapshot)
        for factory in (
            lambda: SecretMaterial(bytearray()),
            lambda: SyntheticNoticeAdapter(
                destination=injected,
                resource_id=self.resource_id,
                expected_secret=invalid_destination_secret,
            ),
            lambda: SyntheticNoticeAdapter(
                destination=self.destination,
                resource_id=injected,
                expected_secret=invalid_resource_secret,
            ),
        ):
            try:
                factory()
            except Exception as exc:
                failures.append(exc)
        self.assertEqual(len(failures), 3)
        self.assertTrue(all(value == 0 for value in invalid_destination_secret))
        self.assertTrue(all(value == 0 for value in invalid_resource_secret))
        self.assert_no_secret(self.expected_snapshot, failures)

    def test_malicious_outcome_and_exception_are_sanitized_without_echo(self):
        injected = self.expected_snapshot.decode("ascii")

        class MaliciousOutcomeAdapter:
            def execute(self, request: object, secret: object) -> object:
                return {"result": injected}

        class MaliciousExceptionAdapter:
            def execute(self, request: object, secret: object) -> AdapterOutcome:
                raise RuntimeError(injected)

        stdout = io.StringIO()
        stderr = io.StringIO()
        results: list[AdapterOutcome] = []
        with redirect_stdout(stdout), redirect_stderr(stderr):
            for candidate in (MaliciousOutcomeAdapter(), MaliciousExceptionAdapter()):
                material, owned = self.material()
                results.append(execute_synthetic_adapter(candidate, self.request(), material))
                self.assertTrue(all(value == 0 for value in owned))
        self.assertEqual(
            [result.code for result in results],
            [AdapterCode.ADAPTER_PROTOCOL_ERROR, AdapterCode.ADAPTER_FAILURE],
        )
        self.assert_no_secret(
            self.expected_snapshot,
            results, stdout.getvalue(), stderr.getvalue(), self.adapter.recorded_calls,
        )

    def test_mismatched_success_receipt_is_sanitized(self):
        class WrongReceiptAdapter:
            def execute(
                self,
                request: SyntheticAdapterRequest,
                secret: SecretMaterial,
            ) -> AdapterOutcome:
                return AdapterOutcome(
                    AdapterCode.DELIVERED,
                    SyntheticNoticeReceipt(str(uuid4()), str(uuid4())),
                )

        material, owned = self.material()
        result = execute_synthetic_adapter(WrongReceiptAdapter(), self.request(), material)
        self.assertEqual(result.code, AdapterCode.ADAPTER_PROTOCOL_ERROR)
        self.assertIsNone(result.receipt)
        self.assertTrue(all(value == 0 for value in owned))

    def test_module_has_no_forbidden_dependencies(self):
        source = (ROOT / "phase8f" / "synthetic_adapter.py").read_text("utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )
        self.assertTrue({
            "socket", "subprocess", "logging", "pathlib", "os", "requests",
            "urllib", "http", "openai", "provider", "controller", "memory",
            "resident_host", "runtime_context", "operator_cli",
        }.isdisjoint(imports))


if __name__ == "__main__":
    unittest.main()
