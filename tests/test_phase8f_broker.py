"""Integrated adversarial tests for the synthetic-only Phase 8F broker."""

from __future__ import annotations

import ast
import base64
import io
import json
import secrets
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import phase8f.broker as broker_module
from phase8f.broker import (
    BrokerCode,
    BrokerError,
    ExactGrantApproval,
    GrantKind,
    GrantProposalRequest,
    GrantRevocationApproval,
    GrantStatus,
    PendingResolutionApproval,
    RegisteredAdapter,
    SecretProvisionRequest,
    SecretRollbackApproval,
    SyntheticSecretBroker,
)
from phase8f.crypto import WindowsCngAesGcm
from phase8f.protocol import (
    AuthenticatedLocalProtocol,
    ProtocolRequest,
    generate_nonce,
)
from phase8f.synthetic_adapter import (
    NOTICE_DELIVER_OPERATION,
    SyntheticNoticeAdapter,
)


ROOT = Path(__file__).resolve().parents[1]


def new_uuid() -> str:
    return str(uuid.uuid4())


def zero(buffer: bytearray) -> None:
    for index in range(len(buffer)):
        buffer[index] = 0


class MutableClock:
    def __init__(self, value: datetime):
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def set(self, value: datetime) -> None:
        self.value = value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


class Phase8FBrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = (Path(self.temporary.name) / "broker").resolve()
        self.initial_time = datetime(2026, 9, 2, 19, 0, tzinfo=timezone.utc)
        self.clock = MutableClock(self.initial_time)
        self.caller_id = "synthetic.caller.fixture"
        self.key_id = "synthetic.key.primary"
        self.adapter_id = "synthetic.notice.adapter"
        self.destination_id = "synthetic://notice/focused-test"
        self.resource_id = new_uuid()
        self.scope_id = "synthetic-task:phase8f-test"

        self.secret_probe = bytearray(secrets.token_urlsafe(48).encode("ascii"))
        self.adapter_expected = bytearray(self.secret_probe)
        self.adapter = SyntheticNoticeAdapter(
            destination=self.destination_id,
            resource_id=self.resource_id,
            expected_secret=self.adapter_expected,
        )
        registration = RegisteredAdapter(
            adapter_id=self.adapter_id,
            operation_id=NOTICE_DELIVER_OPERATION,
            destination_id=self.destination_id,
            resource_id=self.resource_id,
            adapter=self.adapter,
        )

        cipher_key = bytearray(secrets.token_bytes(32))
        cipher = WindowsCngAesGcm(cipher_key, key_id="synthetic-vault-key-v1")
        self.assertTrue(all(value == 0 for value in cipher_key))

        self.protocol_key = bytearray(secrets.token_bytes(32))
        protocol = AuthenticatedLocalProtocol(
            caller_id=self.caller_id,
            key_id=self.key_id,
            key_material=bytearray(self.protocol_key),
        )
        self.broker = SyntheticSecretBroker.initialize(
            self.root,
            cipher=cipher,
            protocol=protocol,
            caller_id=self.caller_id,
            key_id=self.key_id,
            adapters=(registration,),
            clock=self.clock,
        )
        self.protocol = protocol

    def tearDown(self) -> None:
        self.broker.close()
        self.adapter.close()
        zero(self.protocol_key)
        zero(self.secret_probe)
        self.temporary.cleanup()

    def provision(self) -> tuple[str, object]:
        before = self.broker.current_snapshot()
        supplied = bytearray(self.secret_probe)
        result = self.broker.provision_secret(
            SecretProvisionRequest(
                operation_id=new_uuid(),
                expected_generation_id=before.generation_id,
                provisioner_id="synthetic_fixture_maintainer",
                adapter_id=self.adapter_id,
                operation=NOTICE_DELIVER_OPERATION,
                destination_id=self.destination_id,
            ),
            supplied,
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.code, BrokerCode.SECRET_PROVISIONED)
        self.assertIsNotNone(result.secret_ref)
        self.assertTrue(all(value == 0 for value in supplied))
        return result.secret_ref or "", result

    def create_grant(
        self,
        *,
        kind: GrantKind = GrantKind.ONE_TIME,
        secret_ref: str | None = None,
        scope_id: str | None = None,
        max_uses: int | None = None,
        not_before: datetime | None = None,
        expires_at: datetime | None = None,
        review_at: datetime | None = None,
    ) -> tuple[object, ExactGrantApproval, object]:
        if secret_ref is None:
            secret_ref, _ = self.provision()
        now = self.clock()
        start = not_before or now - timedelta(minutes=1)
        if kind is GrantKind.ONE_TIME:
            uses = 1 if max_uses is None else max_uses
            end = expires_at or now + timedelta(hours=1)
            review = review_at
        else:
            uses = 3 if max_uses is None else max_uses
            end = expires_at or now + timedelta(hours=4)
            review = review_at or now + timedelta(hours=3)
        proposal = self.broker.propose_grant(
            GrantProposalRequest(
                operation_id=new_uuid(),
                expected_generation_id=self.broker.current_snapshot().generation_id,
                grant_kind=kind.value,
                caller_id=self.caller_id,
                key_id=self.key_id,
                scope_id=scope_id or self.scope_id,
                resource_id=self.resource_id,
                secret_ref=secret_ref,
                secret_version=1,
                adapter_id=self.adapter_id,
                operation=NOTICE_DELIVER_OPERATION,
                destination_id=self.destination_id,
                not_before=start,
                expires_at=end,
                max_uses=uses,
                review_at=review,
            )
        )
        self.assertTrue(proposal.accepted)
        self.assertEqual(proposal.code, BrokerCode.GRANT_PROPOSED)
        approval = ExactGrantApproval(
            operation_id=new_uuid(),
            expected_generation_id=proposal.generation_id or "",
            proposal_id=proposal.proposal_id or "",
            proposal_digest=proposal.proposal_digest or "",
            source_turn_id=new_uuid(),
            channel="typed_turn",
        )
        granted = self.broker.approve_grant(approval)
        self.assertTrue(granted.accepted)
        self.assertEqual(granted.code, BrokerCode.GRANT_APPROVED)
        return proposal, approval, granted

    def request_for(
        self,
        source_grant_id: str,
        *,
        request_id: str | None = None,
        nonce: str | None = None,
        issued_at: datetime | None = None,
        **overrides: object,
    ) -> ProtocolRequest:
        grant = self.broker.grant_record(source_grant_id)
        values: dict[str, object] = {
            "schema_version": 1,
            "request_id": request_id or new_uuid(),
            "grant_id": source_grant_id,
            "grant_version": grant["version"],
            "expected_generation_id": self.broker.current_snapshot().generation_id,
            "caller_id": grant["caller_id"],
            "key_id": grant["key_id"],
            "adapter_id": grant["adapter_id"],
            "operation_id": grant["operation"],
            "destination_id": grant["destination_id"],
            "scope_id": grant["scope_id"],
            "resource_id": grant["resource_id"],
            "opaque_secret_ref": grant["secret_ref"],
            "issued_at": issued_at or self.clock(),
            "nonce": nonce or generate_nonce(),
            "payload": {"notice_id": new_uuid()},
        }
        values.update(overrides)
        return ProtocolRequest(**values)  # type: ignore[arg-type]

    def execute_request(self, request: ProtocolRequest):
        return self.broker.execute(self.protocol.encode(request))

    def assert_secret_absent(self, *surfaces: object) -> None:
        raw = bytes(self.secret_probe)
        variants = (
            raw,
            raw.hex().encode("ascii"),
            base64.b64encode(raw),
            base64.urlsafe_b64encode(raw),
        )
        rendered = b"\n".join(
            surface if isinstance(surface, bytes)
            else str(surface).encode("utf-8", errors="backslashreplace")
            for surface in surfaces
        )
        self.assertFalse(any(candidate and candidate in rendered for candidate in variants))

    def test_one_time_grant_reserves_before_dispatch_and_replay_is_idempotent(self):
        _, _, granted = self.create_grant()
        request = self.request_for(granted.grant_id)
        encoded = self.protocol.encode(request)

        result = self.broker.execute(encoded)

        self.assertTrue(result.accepted)
        self.assertEqual(result.code, BrokerCode.OPERATION_SUCCEEDED)
        self.assertEqual(result.receipt_notice_id, request.payload["notice_id"])
        grant = self.broker.grant_record(granted.grant_id)
        self.assertEqual(grant["status"], GrantStatus.EXHAUSTED.value)
        self.assertEqual(grant["uses_reserved"], 1)
        self.assertEqual(grant["version"], 2)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

        replay = self.broker.execute(encoded)
        self.assertTrue(replay.accepted)
        self.assertEqual(replay.code, BrokerCode.OPERATION_SUCCEEDED)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

        exhausted = self.execute_request(self.request_for(granted.grant_id))
        self.assertFalse(exhausted.accepted)
        self.assertEqual(exhausted.code, BrokerCode.GRANT_EXHAUSTED)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

    def test_standing_grant_allows_bounded_uses_then_exhausts(self):
        _, _, granted = self.create_grant(kind=GrantKind.STANDING, max_uses=3)
        results = []
        for _ in range(3):
            results.append(self.execute_request(self.request_for(granted.grant_id)))

        self.assertTrue(all(result.accepted for result in results))
        self.assertTrue(all(
            result.code is BrokerCode.OPERATION_SUCCEEDED for result in results
        ))
        grant = self.broker.grant_record(granted.grant_id)
        self.assertEqual(grant["status"], GrantStatus.EXHAUSTED.value)
        self.assertEqual(grant["uses_reserved"], 3)
        self.assertEqual(grant["version"], 4)
        self.assertEqual(len(self.adapter.recorded_calls), 3)

        denied = self.execute_request(self.request_for(granted.grant_id))
        self.assertEqual(denied.code, BrokerCode.GRANT_EXHAUSTED)
        self.assertEqual(len(self.adapter.recorded_calls), 3)

    def test_review_and_expiry_edges_fail_closed_without_dispatch(self):
        review_at = self.initial_time + timedelta(minutes=10)
        expires_at = self.initial_time + timedelta(minutes=20)
        _, _, granted = self.create_grant(
            kind=GrantKind.STANDING,
            max_uses=5,
            review_at=review_at,
            expires_at=expires_at,
        )

        self.clock.set(review_at)
        review_due = self.execute_request(self.request_for(granted.grant_id))
        self.assertEqual(review_due.code, BrokerCode.GRANT_REVIEW_REQUIRED)

        self.clock.set(expires_at)
        expired = self.execute_request(self.request_for(granted.grant_id))
        self.assertEqual(expired.code, BrokerCode.GRANT_EXPIRED)
        self.assertEqual(self.adapter.recorded_calls, ())

    def test_grant_shape_bounds_and_inert_proposal_are_enforced(self):
        with self.assertRaisesRegex(
            BrokerError, "^registered adapter is not allowed$"
        ):
            RegisteredAdapter(
                adapter_id="synthetic.notice.untrusted",
                operation_id=NOTICE_DELIVER_OPERATION,
                destination_id=self.destination_id,
                resource_id=self.resource_id,
                adapter=object(),  # type: ignore[arg-type]
            )

        secret_ref, _ = self.provision()
        invalid = self.broker.propose_grant(
            GrantProposalRequest(
                operation_id=new_uuid(),
                expected_generation_id=self.broker.current_snapshot().generation_id,
                grant_kind=GrantKind.STANDING.value,
                caller_id=self.caller_id,
                key_id=self.key_id,
                scope_id=self.scope_id,
                resource_id=self.resource_id,
                secret_ref=secret_ref,
                secret_version=1,
                adapter_id=self.adapter_id,
                operation=NOTICE_DELIVER_OPERATION,
                destination_id=self.destination_id,
                not_before=self.clock() - timedelta(minutes=1),
                expires_at=self.clock() + timedelta(hours=2),
                max_uses=1,
                review_at=self.clock() + timedelta(hours=1),
            )
        )
        self.assertFalse(invalid.accepted)
        self.assertEqual(invalid.code, BrokerCode.INVALID_REQUEST)

        proposal_request = GrantProposalRequest(
            operation_id=new_uuid(),
            expected_generation_id=self.broker.current_snapshot().generation_id,
            grant_kind=GrantKind.ONE_TIME.value,
            caller_id=self.caller_id,
            key_id=self.key_id,
            scope_id=self.scope_id,
            resource_id=self.resource_id,
            secret_ref=secret_ref,
            secret_version=1,
            adapter_id=self.adapter_id,
            operation=NOTICE_DELIVER_OPERATION,
            destination_id=self.destination_id,
            not_before=self.clock() - timedelta(minutes=1),
            expires_at=self.clock() + timedelta(hours=1),
            max_uses=1,
        )
        for malformed_scope in (
            "synthetic-task:",
            "synthetic-project:",
            "synthetic-task:two:parts",
            "synthetic-task:-leading",
            "synthetic-project:trailing-",
            "synthetic-task:two..parts",
        ):
            with self.subTest(scope=malformed_scope):
                malformed = self.broker.propose_grant(
                    replace(proposal_request, scope_id=malformed_scope)
                )
                self.assertEqual(malformed.code, BrokerCode.INVALID_REQUEST)
        proposed = self.broker.propose_grant(proposal_request)
        self.assertTrue(proposed.accepted)
        self.assertEqual(self.broker.current_snapshot().grant_count, 0)

        no_grant = ProtocolRequest(
            schema_version=1,
            request_id=new_uuid(),
            grant_id=new_uuid(),
            grant_version=1,
            expected_generation_id=self.broker.current_snapshot().generation_id,
            caller_id=self.caller_id,
            key_id=self.key_id,
            adapter_id=self.adapter_id,
            operation_id=NOTICE_DELIVER_OPERATION,
            destination_id=self.destination_id,
            scope_id=self.scope_id,
            resource_id=self.resource_id,
            opaque_secret_ref=secret_ref,
            issued_at=self.clock(),
            nonce=generate_nonce(),
            payload={"notice_id": new_uuid()},
        )
        denied = self.execute_request(no_grant)
        self.assertEqual(denied.code, BrokerCode.CAPABILITY_DENIED)
        self.assertEqual(self.adapter.recorded_calls, ())

        approval = ExactGrantApproval(
            operation_id=new_uuid(),
            expected_generation_id=proposed.generation_id or "",
            proposal_id=proposed.proposal_id or "",
            proposal_digest="0" * 64,
            source_turn_id=new_uuid(),
            channel="typed_turn",
        )
        mismatch = self.broker.approve_grant(approval)
        self.assertEqual(mismatch.code, BrokerCode.APPROVAL_MISMATCH)

        exact = replace(approval, proposal_digest=proposed.proposal_digest or "")
        granted = self.broker.approve_grant(exact)
        self.assertEqual(granted.code, BrokerCode.GRANT_APPROVED)
        replay = self.broker.approve_grant(exact)
        self.assertEqual(replay.code, BrokerCode.IDEMPOTENT_REPLAY)
        self.assertTrue(replay.idempotent_replay)
        conflict = self.broker.approve_grant(
            replace(exact, source_turn_id=new_uuid())
        )
        self.assertEqual(conflict.code, BrokerCode.IDEMPOTENCY_CONFLICT)

    def test_reopen_rejects_untrusted_crypto_protocol_and_identity(self):
        registration = tuple(self.broker._adapters.values())
        common = {
            "root": self.root,
            "caller_id": self.caller_id,
            "key_id": self.key_id,
            "adapters": registration,
            "clock": self.clock,
        }
        with self.assertRaisesRegex(
            BrokerError, "^broker cryptographic configuration is invalid$"
        ):
            SyntheticSecretBroker(
                cipher=object(),  # type: ignore[arg-type]
                protocol=self.protocol,
                **common,
            )
        with self.assertRaisesRegex(
            BrokerError, "^broker cryptographic configuration is invalid$"
        ):
            SyntheticSecretBroker(
                cipher=self.broker._cipher,
                protocol=object(),  # type: ignore[arg-type]
                **common,
            )

        alternate = AuthenticatedLocalProtocol(
            caller_id="synthetic.caller.other",
            key_id=self.key_id,
            key_material=bytearray(self.protocol_key),
        )
        try:
            with self.assertRaisesRegex(
                BrokerError, "^broker protocol identity is invalid$"
            ):
                SyntheticSecretBroker(
                    cipher=self.broker._cipher,
                    protocol=alternate,
                    **common,
                )
        finally:
            alternate.close()

    def test_store_root_rejects_every_nonfixed_drive_type(self):
        candidate = self.root.parent / "nonfixed-broker"
        for drive_type in (0, 1, 2, 4, 5, 6):
            with self.subTest(drive_type=drive_type), patch.object(
                broker_module, "_windows_drive_type", return_value=drive_type
            ):
                with self.assertRaisesRegex(
                    BrokerError, "^broker root must be on a fixed local volume$"
                ):
                    broker_module._validate_root(candidate, must_exist=False)

    def test_metadata_queries_do_not_expand_secret_plaintext(self):
        _, _, granted = self.create_grant(kind=GrantKind.STANDING, max_uses=3)
        with patch.object(
            broker_module,
            "_unpack_vault",
            side_effect=AssertionError("vault plaintext was expanded"),
        ):
            snapshot = self.broker.current_snapshot()
            audit = self.broker.audit_events()
            grant = self.broker.grant_record(granted.grant_id or "")

        self.assertEqual(snapshot.grant_count, 1)
        self.assertGreater(len(audit), 0)
        self.assertEqual(grant["grant_id"], granted.grant_id)

    def test_exact_bindings_and_authenticated_identity_default_deny(self):
        _, _, granted = self.create_grant(
            kind=GrantKind.STANDING,
            max_uses=10,
        )
        grant_id = granted.grant_id or ""
        cases = (
            {"scope_id": "synthetic-task:other"},
            {"resource_id": new_uuid()},
            {"opaque_secret_ref": "sec_" + secrets.token_hex(16)},
            {"adapter_id": "synthetic.notice.other"},
            {"operation_id": "synthetic.notice.preview"},
            {"destination_id": "synthetic://notice/other"},
            {"grant_id": new_uuid()},
            {"payload": {"notice_id": new_uuid(), "extra": "denied"}},
            {"payload": {"notice_id": "not-a-uuid"}},
        )
        for overrides in cases:
            with self.subTest(overrides=tuple(overrides)):
                result = self.execute_request(
                    self.request_for(grant_id, **overrides)
                )
                self.assertEqual(result.code, BrokerCode.CAPABILITY_DENIED)

        stale_version = self.execute_request(
            self.request_for(grant_id, grant_version=2)
        )
        self.assertEqual(stale_version.code, BrokerCode.STALE_STATE)
        stale_generation = self.execute_request(
            self.request_for(grant_id, expected_generation_id=new_uuid())
        )
        self.assertEqual(stale_generation.code, BrokerCode.STALE_STATE)

        wrong_caller = self.request_for(
            grant_id, caller_id="synthetic.caller.other"
        )
        alternate = AuthenticatedLocalProtocol(
            caller_id="synthetic.caller.other",
            key_id=self.key_id,
            key_material=bytearray(self.protocol_key),
        )
        try:
            rejected = self.broker.execute(alternate.encode(wrong_caller))
        finally:
            alternate.close()
        self.assertEqual(rejected.code, BrokerCode.AUTHENTICATION_FAILED)

        correct = self.protocol.encode(self.request_for(grant_id))
        wire = bytearray(correct)
        wire[-2] = ord("0") if wire[-2] != ord("0") else ord("1")
        tampered = self.broker.execute(wire)
        self.assertEqual(tampered.code, BrokerCode.AUTHENTICATION_FAILED)
        self.assertEqual(self.adapter.recorded_calls, ())

    def test_revocation_is_exact_versioned_and_replay_safe(self):
        _, _, granted = self.create_grant(
            kind=GrantKind.STANDING,
            max_uses=5,
        )
        grant_id = granted.grant_id or ""
        base = GrantRevocationApproval(
            operation_id=new_uuid(),
            expected_generation_id=self.broker.current_snapshot().generation_id,
            grant_id=grant_id,
            expected_grant_version=2,
            source_turn_id=new_uuid(),
            channel="ptt_release",
        )
        stale = self.broker.revoke_grant(base)
        self.assertEqual(stale.code, BrokerCode.STALE_STATE)

        exact = replace(base, expected_grant_version=1)
        revoked = self.broker.revoke_grant(exact)
        self.assertTrue(revoked.accepted)
        self.assertEqual(revoked.code, BrokerCode.GRANT_REVOKED)
        self.assertEqual(revoked.grant_version, 2)

        denied = self.execute_request(self.request_for(grant_id))
        self.assertEqual(denied.code, BrokerCode.GRANT_REVOKED)
        replay = self.broker.revoke_grant(exact)
        self.assertEqual(replay.code, BrokerCode.IDEMPOTENT_REPLAY)
        self.assertTrue(replay.idempotent_replay)
        conflict = self.broker.revoke_grant(
            replace(exact, source_turn_id=new_uuid())
        )
        self.assertEqual(conflict.code, BrokerCode.IDEMPOTENCY_CONFLICT)
        self.assertEqual(self.adapter.recorded_calls, ())

    def test_request_and_nonce_replay_are_persistently_rejected(self):
        _, _, granted = self.create_grant(
            kind=GrantKind.STANDING,
            max_uses=5,
        )
        grant_id = granted.grant_id or ""
        request = self.request_for(grant_id)
        encoded = self.protocol.encode(request)
        first = self.broker.execute(encoded)
        self.assertEqual(first.code, BrokerCode.OPERATION_SUCCEEDED)

        replay = self.broker.execute(encoded)
        self.assertEqual(replay.code, BrokerCode.OPERATION_SUCCEEDED)
        self.assertTrue(replay.idempotent_replay)

        conflicting = self.request_for(
            grant_id,
            request_id=request.request_id,
            payload={"notice_id": new_uuid()},
        )
        conflict = self.execute_request(conflicting)
        self.assertEqual(conflict.code, BrokerCode.REPLAY_CONFLICT)

        reused_nonce = self.request_for(grant_id, nonce=request.nonce)
        nonce_replay = self.execute_request(reused_nonce)
        self.assertEqual(nonce_replay.code, BrokerCode.REPLAY_DENIED)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

        self.clock.advance(timedelta(minutes=3))
        aged_replay = self.broker.execute(encoded)
        self.assertEqual(aged_replay.code, BrokerCode.OPERATION_SUCCEEDED)
        self.assertTrue(aged_replay.idempotent_replay)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

    def test_request_issued_before_not_before_cannot_age_into_authority(self):
        not_before = self.clock() + timedelta(seconds=30)
        _, _, granted = self.create_grant(
            kind=GrantKind.STANDING,
            max_uses=3,
            not_before=not_before,
            expires_at=self.clock() + timedelta(hours=1),
            review_at=self.clock() + timedelta(minutes=30),
        )
        grant_id = granted.grant_id or ""
        premature = self.request_for(grant_id)
        encoded = self.protocol.encode(premature)

        first = self.broker.execute(encoded)
        self.assertEqual(first.code, BrokerCode.GRANT_NOT_YET_VALID)
        self.clock.advance(timedelta(seconds=31))
        repeated = self.broker.execute(encoded)
        self.assertEqual(repeated.code, BrokerCode.GRANT_NOT_YET_VALID)
        self.assertEqual(self.adapter.recorded_calls, ())

        fresh = self.execute_request(self.request_for(grant_id))
        self.assertEqual(fresh.code, BrokerCode.OPERATION_SUCCEEDED)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

    def test_failed_reservation_never_dispatches_or_consumes_grant(self):
        _, _, granted = self.create_grant()
        grant_id = granted.grant_id or ""
        request = self.request_for(grant_id)
        encoded = self.protocol.encode(request)

        with patch.object(
            self.broker,
            "_commit_state",
            side_effect=BrokerError("synthetic persistence failure"),
        ):
            failed = self.broker.execute(encoded)

        self.assertEqual(failed.code, BrokerCode.RESERVATION_FAILED)
        self.assertEqual(self.adapter.recorded_calls, ())
        unchanged = self.broker.grant_record(grant_id)
        self.assertEqual(unchanged["version"], 1)
        self.assertEqual(unchanged["uses_reserved"], 0)
        self.assertEqual(unchanged["status"], GrantStatus.ACTIVE.value)

        retry = self.broker.execute(encoded)
        self.assertEqual(retry.code, BrokerCode.OPERATION_SUCCEEDED)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

    def test_uncertain_pointer_selection_never_dispatches(self):
        _, _, granted = self.create_grant()
        grant_id = granted.grant_id or ""
        request = self.request_for(grant_id)
        encoded = self.protocol.encode(request)
        original_read = self.broker._read_current_pointer
        count = 0

        def fail_post_selection_read():
            nonlocal count
            count += 1
            if count == 2:
                raise BrokerError("synthetic pointer verification failure")
            return original_read()

        with patch.object(
            self.broker,
            "_read_current_pointer",
            side_effect=fail_post_selection_read,
        ):
            uncertain = self.broker.execute(encoded)

        self.assertEqual(uncertain.code, BrokerCode.OUTCOME_UNCERTAIN)
        self.assertEqual(self.adapter.recorded_calls, ())
        replay = self.broker.execute(encoded)
        self.assertEqual(replay.code, BrokerCode.OUTCOME_UNCERTAIN)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(self.adapter.recorded_calls, ())
        grant = self.broker.grant_record(grant_id)
        self.assertEqual(grant["uses_reserved"], 1)

    def test_resolution_cannot_race_a_live_dispatch(self):
        _, _, granted = self.create_grant(kind=GrantKind.STANDING, max_uses=3)
        request = self.request_for(granted.grant_id or "")
        encoded = self.protocol.encode(request)
        entered = threading.Event()
        release = threading.Event()
        original_execute = broker_module.execute_synthetic_adapter

        def blocked_execute(adapter, adapter_request, secret):
            entered.set()
            if not release.wait(timeout=10):
                raise RuntimeError("synthetic adapter synchronization failed")
            return original_execute(adapter, adapter_request, secret)

        with patch.object(
            broker_module,
            "execute_synthetic_adapter",
            side_effect=blocked_execute,
        ), ThreadPoolExecutor(max_workers=2) as executor:
            execute_future = executor.submit(self.broker.execute, encoded)
            self.assertTrue(entered.wait(timeout=10))
            pointer = json.loads((self.root / "current.json").read_text("ascii"))
            resolution = PendingResolutionApproval(
                operation_id=new_uuid(),
                expected_generation_id=pointer["generation_id"],
                request_id=request.request_id,
                source_turn_id=new_uuid(),
                channel="typed_turn",
            )
            resolve_future = executor.submit(self.broker.resolve_uncertain, resolution)
            try:
                with self.assertRaises(FutureTimeoutError):
                    resolve_future.result(timeout=0.5)
            finally:
                release.set()
            executed = execute_future.result(timeout=10)
            resolved = resolve_future.result(timeout=10)

        self.assertEqual(executed.code, BrokerCode.OPERATION_SUCCEEDED)
        self.assertEqual(resolved.code, BrokerCode.STALE_STATE)
        replay = self.broker.execute(encoded)
        self.assertEqual(replay.code, BrokerCode.OPERATION_SUCCEEDED)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

    def test_uncertain_completion_is_not_redispatched_and_requires_resolution(self):
        secret_ref, _ = self.provision()
        rollback_target = self.broker.current_snapshot()
        _, _, granted = self.create_grant(
            kind=GrantKind.STANDING,
            secret_ref=secret_ref,
            max_uses=5,
        )
        grant_id = granted.grant_id or ""
        request = self.request_for(grant_id)
        encoded = self.protocol.encode(request)
        original_commit = self.broker._commit_state
        count = 0

        def fail_second_commit(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise BrokerError("synthetic completion failure")
            return original_commit(*args, **kwargs)

        with patch.object(self.broker, "_commit_state", side_effect=fail_second_commit):
            uncertain = self.broker.execute(encoded)

        self.assertEqual(uncertain.code, BrokerCode.OUTCOME_UNCERTAIN)
        self.assertEqual(len(self.adapter.recorded_calls), 1)
        replay = self.broker.execute(encoded)
        self.assertEqual(replay.code, BrokerCode.OUTCOME_UNCERTAIN)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

        rollback = SecretRollbackApproval(
            operation_id=new_uuid(),
            expected_generation_id=self.broker.current_snapshot().generation_id,
            target_generation_id=rollback_target.generation_id,
            target_manifest_sha256=rollback_target.manifest_sha256,
            source_turn_id=new_uuid(),
            channel="typed_turn",
        )
        pending = self.broker.rollback_secrets(rollback)
        self.assertEqual(pending.code, BrokerCode.PENDING_OPERATION)

        resolution = PendingResolutionApproval(
            operation_id=new_uuid(),
            expected_generation_id=self.broker.current_snapshot().generation_id,
            request_id=request.request_id,
            source_turn_id=new_uuid(),
            channel="typed_turn",
        )
        closed = self.broker.resolve_uncertain(resolution)
        self.assertEqual(closed.code, BrokerCode.UNCERTAIN_REQUEST_CLOSED)
        resolved_replay = self.broker.resolve_uncertain(resolution)
        self.assertEqual(resolved_replay.code, BrokerCode.IDEMPOTENT_REPLAY)
        resolution_conflict = self.broker.resolve_uncertain(
            replace(resolution, source_turn_id=new_uuid())
        )
        self.assertEqual(
            resolution_conflict.code, BrokerCode.IDEMPOTENCY_CONFLICT
        )

        final_replay = self.broker.execute(encoded)
        self.assertEqual(final_replay.code, BrokerCode.OUTCOME_UNCERTAIN)
        self.assertTrue(final_replay.idempotent_replay)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

    def test_authenticated_pointer_and_generation_tampering_fail_closed(self):
        self.provision()
        pointer_path = self.root / "current.json"
        original_pointer = pointer_path.read_bytes()
        pointer = json.loads(original_pointer)
        pointer["manifest_sha256"] = (
            ("0" if pointer["manifest_sha256"][0] != "0" else "1")
            + pointer["manifest_sha256"][1:]
        )
        pointer_path.write_text(
            json.dumps(pointer, ensure_ascii=True, sort_keys=True),
            encoding="ascii",
        )
        try:
            with self.assertRaises(BrokerError) as pointer_failure:
                self.broker.current_snapshot()
            self.assertEqual(
                str(pointer_failure.exception),
                "current broker pointer is unavailable",
            )
        finally:
            pointer_path.write_bytes(original_pointer)

        snapshot = self.broker.current_snapshot()
        digest_path = (
            self.root / "generations" / snapshot.generation_id /
            "manifest.sha256"
        )
        original_digest = digest_path.read_bytes()
        digest_path.write_bytes(original_digest + b" ")
        try:
            with self.assertRaises(BrokerError):
                self.broker.current_snapshot()
        finally:
            digest_path.write_bytes(original_digest)

        vault_path = self.root / "generations" / snapshot.generation_id / "vault.json"
        original_vault = vault_path.read_bytes()
        vault_path.write_bytes(original_vault + b" ")
        try:
            with self.assertRaises(BrokerError) as generation_failure:
                self.broker.current_snapshot()
            self.assertEqual(
                str(generation_failure.exception),
                "broker generation is unavailable",
            )
        finally:
            vault_path.write_bytes(original_vault)
        self.broker.current_snapshot()

    def test_clock_rollback_blocks_execution_without_dispatch(self):
        _, _, granted = self.create_grant(
            kind=GrantKind.STANDING,
            max_uses=5,
        )
        grant_id = granted.grant_id or ""
        self.clock.advance(timedelta(minutes=1))
        succeeded = self.execute_request(self.request_for(grant_id))
        self.assertEqual(succeeded.code, BrokerCode.OPERATION_SUCCEEDED)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

        self.clock.set(self.initial_time)
        rolled_back = self.execute_request(self.request_for(grant_id))
        self.assertEqual(rolled_back.code, BrokerCode.CLOCK_UNTRUSTED)
        self.assertEqual(len(self.adapter.recorded_calls), 1)

    def test_secret_rollback_preserves_authority_state_and_holds_active_grants(self):
        secret_ref, _ = self.provision()
        target = self.broker.current_snapshot()
        _, _, active = self.create_grant(
            kind=GrantKind.STANDING,
            secret_ref=secret_ref,
            max_uses=5,
        )
        _, _, revoked = self.create_grant(
            kind=GrantKind.STANDING,
            secret_ref=secret_ref,
            scope_id="synthetic-task:revoked",
            max_uses=5,
        )
        revoked_id = revoked.grant_id or ""
        revoke = GrantRevocationApproval(
            operation_id=new_uuid(),
            expected_generation_id=self.broker.current_snapshot().generation_id,
            grant_id=revoked_id,
            expected_grant_version=1,
            source_turn_id=new_uuid(),
            channel="typed_turn",
        )
        self.assertEqual(
            self.broker.revoke_grant(revoke).code, BrokerCode.GRANT_REVOKED
        )

        approval = SecretRollbackApproval(
            operation_id=new_uuid(),
            expected_generation_id=self.broker.current_snapshot().generation_id,
            target_generation_id=target.generation_id,
            target_manifest_sha256="0" * 64,
            source_turn_id=new_uuid(),
            channel="ptt_release",
        )
        mismatch = self.broker.rollback_secrets(approval)
        self.assertEqual(mismatch.code, BrokerCode.APPROVAL_MISMATCH)

        exact = replace(approval, target_manifest_sha256=target.manifest_sha256)
        restored = self.broker.rollback_secrets(exact)
        self.assertEqual(restored.code, BrokerCode.SECRETS_ROLLED_BACK)
        self.assertNotEqual(restored.generation_id, target.generation_id)

        active_id = active.grant_id or ""
        active_record = self.broker.grant_record(active_id)
        revoked_record = self.broker.grant_record(revoked_id)
        self.assertEqual(active_record["status"], GrantStatus.RECOVERY_HOLD.value)
        self.assertEqual(active_record["version"], 2)
        self.assertEqual(revoked_record["status"], GrantStatus.REVOKED.value)
        self.assertEqual(revoked_record["version"], 2)

        held = self.execute_request(self.request_for(active_id))
        denied = self.execute_request(self.request_for(revoked_id))
        self.assertEqual(held.code, BrokerCode.GRANT_RECOVERY_HOLD)
        self.assertEqual(denied.code, BrokerCode.GRANT_REVOKED)
        self.assertEqual(self.adapter.recorded_calls, ())

        replay = self.broker.rollback_secrets(exact)
        self.assertEqual(replay.code, BrokerCode.IDEMPOTENT_REPLAY)
        conflict = self.broker.rollback_secrets(
            replace(exact, source_turn_id=new_uuid())
        )
        self.assertEqual(conflict.code, BrokerCode.IDEMPOTENCY_CONFLICT)

    def test_secret_plaintext_never_appears_in_public_or_persistent_surfaces(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            secret_ref, provisioned = self.provision()
            proposal, approval, granted = self.create_grant(
                secret_ref=secret_ref,
            )
            request = self.request_for(granted.grant_id or "")
            result = self.execute_request(request)
            audit = self.broker.audit_events()
            record = self.broker.grant_record(granted.grant_id or "")

        persisted = tuple(
            path.read_bytes() for path in self.root.rglob("*") if path.is_file()
        )
        surfaces = (
            stdout.getvalue(),
            stderr.getvalue(),
            provisioned,
            proposal,
            approval,
            granted,
            request,
            result,
            audit,
            record,
            self.adapter,
            self.adapter.recorded_calls,
            *persisted,
        )
        self.assert_secret_absent(*surfaces)
        for name in ("get_secret", "read_secret", "export_secret"):
            self.assertFalse(hasattr(self.broker, name))

    def test_concurrent_identical_one_time_request_dispatches_once(self):
        _, _, granted = self.create_grant()
        request = self.request_for(granted.grant_id or "")
        encoded = self.protocol.encode(request)
        workers = 6
        barrier = threading.Barrier(workers)

        def invoke():
            barrier.wait(timeout=10)
            return self.broker.execute(encoded)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = tuple(executor.map(lambda _index: invoke(), range(workers)))

        self.assertTrue(
            all(
                item.code in {
                    BrokerCode.OPERATION_SUCCEEDED,
                    BrokerCode.OUTCOME_UNCERTAIN,
                }
                for item in results
            )
        )
        self.assertTrue(
            any(item.code == BrokerCode.OPERATION_SUCCEEDED for item in results)
        )
        self.assertEqual(sum(not item.idempotent_replay for item in results), 1)
        self.assertEqual(len(self.adapter.recorded_calls), 1)
        grant = self.broker.grant_record(granted.grant_id or "")
        self.assertEqual(grant["uses_reserved"], 1)
        self.assertEqual(grant["status"], GrantStatus.EXHAUSTED.value)
        stable = self.broker.execute(encoded)
        self.assertEqual(stable.code, BrokerCode.OPERATION_SUCCEEDED)
        self.assertTrue(stable.idempotent_replay)

    def test_ordinary_runtime_import_does_not_compose_phase8f(self):
        broker_tree = ast.parse((ROOT / "phase8f" / "broker.py").read_text(
            encoding="utf-8"
        ))
        imported_roots: set[str] = set()
        for node in ast.walk(broker_tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".")[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
        self.assertTrue({
            "graci", "http", "logging", "requests", "socket", "subprocess",
            "urllib", "webbrowser",
        }.isdisjoint(imported_roots))

        for source_path in (ROOT / "graci").glob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            imports: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
            self.assertFalse(any(name.startswith("phase8f") for name in imports))

        completed = subprocess.run(
            [
                sys.executable,
                "-W",
                "error",
                "-c",
                (
                    "import sys; import graci.operator_cli; "
                    "print('phase8f' in sys.modules, "
                    "'phase8f.broker' in sys.modules)"
                ),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.stdout.strip(), "False False")
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
