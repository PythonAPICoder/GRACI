"""Deterministic tests for the isolated Phase 8F protocol contract."""

import json
import secrets
import traceback
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from phase8f.protocol import (
    AUTHENTICATION_FAILURE,
    DECODE_FAILURE,
    AuthenticatedLocalProtocol,
    ProtocolAuthenticationError,
    ProtocolClosedError,
    ProtocolDecodeError,
    ProtocolFreshnessError,
    ProtocolRequest,
    ProtocolValidationError,
    generate_nonce,
    request_digest,
    validate_freshness,
)


def canonical_json(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def zero(buffer):
    for index in range(len(buffer)):
        buffer[index] = 0


class Phase8FProtocolTests(unittest.TestCase):
    def setUp(self):
        self._key = bytearray(secrets.token_bytes(32))
        injected = bytearray(self._key)
        self.protocol = AuthenticatedLocalProtocol(
            caller_id="synthetic.caller.fixture",
            key_id="synthetic.key.primary",
            key_material=injected,
        )
        self.assertTrue(all(value == 0 for value in injected))
        self.now = datetime(2026, 9, 2, 18, 30, tzinfo=timezone.utc)

    def tearDown(self):
        self.protocol.close()
        zero(self._key)

    def protocol_for(self, *, caller_id=None, key_id=None):
        return AuthenticatedLocalProtocol(
            caller_id=caller_id or "synthetic.caller.fixture",
            key_id=key_id or "synthetic.key.primary",
            key_material=bytearray(self._key),
        )

    def request(self, **overrides):
        values = {
            "schema_version": 1,
            "request_id": str(uuid.uuid4()),
            "grant_id": str(uuid.uuid4()),
            "grant_version": 3,
            "expected_generation_id": str(uuid.uuid4()),
            "caller_id": "synthetic.caller.fixture",
            "key_id": "synthetic.key.primary",
            "adapter_id": "synthetic.adapter.mail",
            "operation_id": "draft",
            "destination_id": "synthetic.destination.inbox",
            "scope_id": "synthetic.scope.project-a",
            "resource_id": "synthetic.resource.message-a",
            "opaque_secret_ref": "synthetic.secret.fixture-a",
            "issued_at": self.now,
            "nonce": generate_nonce(),
            "payload": {"mode": "preview", "subject": "synthetic fixture"},
        }
        values.update(overrides)
        return ProtocolRequest(**values)

    def decoded_object(self, encoded):
        return json.loads(encoded.decode("ascii"))

    def assert_fixed_failure_without_sentinel(
        self, action, expected_type, expected_message, sentinel
    ):
        try:
            action()
        except expected_type as exception:
            rendered = "".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            )
            self.assertEqual(str(exception), expected_message)
            self.assertIsNone(exception.__cause__)
            self.assertNotIn(sentinel, str(exception))
            self.assertNotIn(sentinel, repr(exception))
            self.assertNotIn(sentinel, rendered)
        else:
            self.fail("expected fixed protocol failure")

    def test_round_trip_binds_grant_version_scope_and_generation(self):
        request = self.request()

        encoded = self.protocol.encode(request)
        decoded = self.protocol.decode(encoded)

        self.assertEqual(decoded, request)
        self.assertEqual(decoded.grant_version, 3)
        self.assertEqual(decoded.scope_id, "synthetic.scope.project-a")
        self.assertEqual(decoded.expected_generation_id, request.expected_generation_id)
        self.assertEqual(request_digest(decoded), request_digest(request))

    def test_exact_synthetic_notice_destination_round_trips(self):
        request = self.request(destination_id="synthetic://notice/focused-test")

        self.assertEqual(
            self.protocol.decode(self.protocol.encode(request)).destination_id,
            "synthetic://notice/focused-test",
        )

    def test_encoding_is_canonical_and_idempotent(self):
        request = self.request()

        first = self.protocol.encode(request)
        second = self.protocol.encode(request)

        self.assertEqual(first, second)
        self.assertEqual(first, canonical_json(self.decoded_object(first)))
        pretty = json.dumps(self.decoded_object(first), indent=2).encode("ascii")
        with self.assertRaisesRegex(ProtocolDecodeError, f"^{DECODE_FAILURE}$"):
            self.protocol.decode(pretty)

    def test_unknown_fields_are_rejected(self):
        envelope = self.decoded_object(self.protocol.encode(self.request()))
        envelope["unexpected"] = "synthetic"
        with self.assertRaisesRegex(ProtocolDecodeError, f"^{DECODE_FAILURE}$"):
            self.protocol.decode(canonical_json(envelope))

        envelope = self.decoded_object(self.protocol.encode(self.request()))
        envelope["request"]["unexpected"] = "synthetic"
        with self.assertRaisesRegex(ProtocolDecodeError, f"^{DECODE_FAILURE}$"):
            self.protocol.decode(canonical_json(envelope))

    def test_envelope_and_payload_size_bounds_fail_closed(self):
        with self.assertRaisesRegex(ProtocolDecodeError, f"^{DECODE_FAILURE}$"):
            self.protocol.decode(b"{" + b"x" * 8192)

        too_many = {f"field{index}": "value" for index in range(13)}
        with self.assertRaises(ProtocolValidationError):
            self.request(payload=too_many)

    def test_duplicate_keys_are_rejected_at_every_object_depth(self):
        envelope = self.decoded_object(self.protocol.encode(self.request()))
        request_text = canonical_json(envelope["request"]).decode("ascii")
        duplicate_envelope = (
            "{\"mac\":"
            + json.dumps(envelope["mac"])
            + ",\"mac\":"
            + json.dumps(envelope["mac"])
            + ",\"request\":"
            + request_text
            + "}"
        ).encode("ascii")
        with self.assertRaisesRegex(ProtocolDecodeError, f"^{DECODE_FAILURE}$"):
            self.protocol.decode(duplicate_envelope)

        payload_text = '\"payload\":{\"mode\":\"preview\",\"subject\":\"synthetic fixture\"}'
        duplicate_payload = (
            '\"payload\":{\"mode\":\"preview\",\"mode\":\"preview\",'
            '\"subject\":\"synthetic fixture\"}'
        )
        self.assertIn(payload_text, request_text)
        request_text = request_text.replace(payload_text, duplicate_payload)
        nested_duplicate = (
            "{\"mac\":"
            + json.dumps(envelope["mac"])
            + ",\"request\":"
            + request_text
            + "}"
        ).encode("ascii")
        with self.assertRaisesRegex(ProtocolDecodeError, f"^{DECODE_FAILURE}$"):
            self.protocol.decode(nested_duplicate)

    def authentication_failure(self, encoded):
        with self.assertRaises(ProtocolAuthenticationError) as caught:
            self.protocol.decode(encoded)
        self.assertEqual(str(caught.exception), AUTHENTICATION_FAILURE)
        self.assertIsNone(caught.exception.__cause__)
        return str(caught.exception)

    def test_bad_mac_wrong_caller_and_wrong_key_have_one_fixed_failure(self):
        envelope = self.decoded_object(self.protocol.encode(self.request()))
        envelope["mac"] = "0" * 64
        bad_mac = self.authentication_failure(canonical_json(envelope))

        wrong_caller_protocol = self.protocol_for(
            caller_id="synthetic.caller.unknown"
        )
        try:
            wrong_caller = wrong_caller_protocol.encode(
                self.request(caller_id="synthetic.caller.unknown")
            )
        finally:
            wrong_caller_protocol.close()
        wrong_caller_failure = self.authentication_failure(wrong_caller)

        wrong_key_protocol = self.protocol_for(key_id="synthetic.key.unknown")
        try:
            wrong_key = wrong_key_protocol.encode(
                self.request(key_id="synthetic.key.unknown")
            )
        finally:
            wrong_key_protocol.close()
        wrong_key_failure = self.authentication_failure(wrong_key)

        self.assertEqual(
            {bad_mac, wrong_caller_failure, wrong_key_failure},
            {AUTHENTICATION_FAILURE},
        )

    def test_parser_uuid_and_unicode_failures_do_not_format_untrusted_input(self):
        sentinel = "runtime-" + uuid.uuid4().hex
        malformed = ("{\"request\":\"" + sentinel).encode("ascii")
        self.assert_fixed_failure_without_sentinel(
            lambda: self.protocol.decode(malformed),
            ProtocolDecodeError,
            DECODE_FAILURE,
            sentinel,
        )

        invalid_unicode = b"\xff" + sentinel.encode("ascii")
        self.assert_fixed_failure_without_sentinel(
            lambda: self.protocol.decode(invalid_unicode),
            ProtocolDecodeError,
            DECODE_FAILURE,
            sentinel,
        )

        self.assert_fixed_failure_without_sentinel(
            lambda: self.request(request_id=sentinel),
            ProtocolValidationError,
            "invalid protocol request",
            sentinel,
        )

    def test_freshness_rejects_stale_and_future_requests(self):
        validate_freshness(self.request(), now=self.now)

        stale = self.request(issued_at=self.now - timedelta(minutes=2, microseconds=1))
        with self.assertRaises(ProtocolFreshnessError):
            validate_freshness(stale, now=self.now)

        future = self.request(issued_at=self.now + timedelta(seconds=10, microseconds=1))
        with self.assertRaises(ProtocolFreshnessError):
            validate_freshness(future, now=self.now)

    def test_malformed_uuids_grant_versions_and_identifiers_are_rejected(self):
        malformed = (
            {"request_id": str(uuid.uuid4()).upper()},
            {"grant_id": str(uuid.UUID(int=0))},
            {"expected_generation_id": "not-a-uuid"},
            {"grant_version": 0},
            {"grant_version": True},
            {"caller_id": "Synthetic Caller"},
            {"scope_id": "../synthetic-scope"},
            {"resource_id": "synthetic/../../resource"},
            {"opaque_secret_ref": ""},
        )
        for override in malformed:
            with self.subTest(field=next(iter(override))):
                with self.assertRaises(ProtocolValidationError) as caught:
                    self.request(**override)
                self.assertIsNone(caught.exception.__cause__)

    def test_malformed_nonce_and_payload_are_rejected(self):
        malformed = (
            {"nonce": "short"},
            {"nonce": "!" * 32},
            {"payload": {"raw_secret": "not permitted"}},
            {"payload": {"api_key": "not permitted"}},
            {"payload": {"mode": 1}},
            {"payload": {"mode": {"nested": "not permitted"}}},
            {"payload": {"mode": "line one\nline two"}},
            {"payload": {"mode": "x" * 257}},
        )
        for override in malformed:
            with self.subTest(override=next(iter(override))):
                with self.assertRaises(ProtocolValidationError) as caught:
                    self.request(**override)
                self.assertIsNone(caught.exception.__cause__)

    def test_wire_has_no_secret_bearing_or_raw_secret_field(self):
        envelope = self.decoded_object(self.protocol.encode(self.request()))
        request_fields = set(envelope["request"])

        self.assertIn("opaque_secret_ref", request_fields)
        self.assertNotIn("secret", request_fields)
        self.assertNotIn("secret_value", request_fields)
        self.assertNotIn("raw_secret", request_fields)
        self.assertNotIn("credential", request_fields)
        self.assertTrue(
            all(
                isinstance(value, str)
                for value in envelope["request"]["payload"].values()
            )
        )

    def test_close_invalidates_protocol_without_exposing_key_material(self):
        request = self.request()
        self.protocol.close()

        self.assertTrue(self.protocol.closed)
        with self.assertRaises(ProtocolClosedError) as caught:
            self.protocol.encode(request)
        self.assertIsNone(caught.exception.__cause__)


if __name__ == "__main__":
    unittest.main()
