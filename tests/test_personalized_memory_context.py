"""Synthetic personalized-memory context adapter tests."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from graci.memory_context import MemoryContextResolution
from graci.personalized_memory import (ExactApproval, PersonalizedMemoryError,
                                      PersonalizedRetrievalResult,
                                      ProposalRequest,
                                      SyntheticPersonalizedMemoryRepository)
from graci.personalized_memory_context import (
    SyntheticPersonalizedMemoryContextProvider)


def synthetic_uuid(number: int) -> str:
    return f"{number:08x}-0000-4000-8000-{number:012x}"


class PersonalizedMemoryContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.now = datetime(2026, 9, 2, 18, 0, tzinfo=timezone.utc)
        generation_ids = iter(synthetic_uuid(0x80000000 + index) for index in range(100))
        self.repository = SyntheticPersonalizedMemoryRepository.initialize(
            self.root / "memory-state",
            clock=lambda: self.now,
            generation_id_factory=lambda: next(generation_ids),
        )
        self.operation = 1

    def tearDown(self):
        self.temp.cleanup()

    def create_approved(self, *, content="Synthetic editor preference.",
                        key="user.synthetic.editor"):
        operation_id = synthetic_uuid(self.operation)
        self.operation += 1
        proposal = self.repository.propose(ProposalRequest(
            operation_id=operation_id, action="create", personalized_kind="preference",
            scope={"kind": "project", "id": "synthetic-project"}, relevance_key=key,
            content=content, source_ref=f"synthetic:turn:{operation_id}",
            source_turn_id=synthetic_uuid(0x10000000 + self.operation),
            proposal_origin="product_owner_direct", source_boundary="typed_turn"))
        self.assertTrue(proposal.accepted)
        stored = self.repository.read_proposal(proposal.proposal_id)
        approval = self.repository.approve(ExactApproval(
            operation_id=synthetic_uuid(0x20000000 + self.operation),
            proposal_id=proposal.proposal_id,
            proposal_digest=stored["proposal_digest"],
            source_turn_id=synthetic_uuid(0x30000000 + self.operation),
            channel="typed_turn"))
        self.assertTrue(approval.accepted)
        return approval

    def provider(self, *, expected_generation_id=None, context=None):
        return SyntheticPersonalizedMemoryContextProvider(
            self.repository,
            context=context or {
                "kind": "project", "project_id": "synthetic-project",
                "session_id": None, "include_global": True, "include_project": False,
            },
            relevance_keys=("user.synthetic.editor",),
            allowed_kinds=("preference",),
            limit=5,
            expected_generation_id=expected_generation_id,
        )

    def test_resolves_one_bounded_approved_synthetic_record(self):
        approval = self.create_approved()
        resolution = self.provider(
            expected_generation_id=self.repository.current_snapshot().generation_id).resolve()
        self.assertEqual(resolution.status, "applied")
        self.assertIsNone(resolution.reason)
        self.assertEqual(resolution.context["record_count"], 1)
        self.assertEqual(resolution.context["records"][0]["memory_id"], approval.memory_id)
        self.assertEqual(resolution.context["classification"], "UNTRUSTED_CONTEXT_DATA")
        self.assertFalse(resolution.context["authority_permitted"])

    def test_no_applicable_synthetic_memory_returns_bounded_failure(self):
        resolution = self.provider().resolve()
        self.assertEqual(resolution.status, "no_applicable_memory")
        self.assertIsNone(resolution.context)
        self.assertIn("no applicable", resolution.reason)

    def test_conflicting_memory_returns_conflict_and_no_context(self):
        self.create_approved(content="Synthetic choice A.")
        self.create_approved(content="Synthetic choice B.")
        resolution = self.provider().resolve()
        self.assertEqual(resolution.status, "memory_conflict")
        self.assertIsNone(resolution.context)

    def test_stale_expected_generation_fails_closed(self):
        expected = self.repository.current_snapshot().generation_id
        self.create_approved()
        resolution = self.provider(expected_generation_id=expected).resolve()
        self.assertEqual(resolution.status, "stale_source")
        self.assertIsNone(resolution.context)

    def _resolve_with_retrieval(self, evidence, records, expected_generation_id=None):
        with patch.object(
                self.repository, "retrieve",
                return_value=PersonalizedRetrievalResult(
                    True, None, records, (), (), evidence)):
            return self.provider(expected_generation_id=expected_generation_id).resolve()

    def _retrieval_record(self, content="Synthetic record content."):
        return {
            "memory_id": synthetic_uuid(0x40000000),
            "personalized_kind": "preference",
            "relevance_key": "user.synthetic.editor",
            "content": content,
        }

    def _retrieval_evidence(self, source_generation_id=...):
        evidence = {
            "schema_version": 1,
            "classification": "UNTRUSTED_CONTEXT_DATA",
            "source_manifest_sha256": "0" * 64,
        }
        if source_generation_id is not ...:
            evidence["source_generation_id"] = source_generation_id
        return evidence

    def test_missing_source_generation_id_returns_memory_unavailable(self):
        resolution = self._resolve_with_retrieval(
            self._retrieval_evidence(), (self._retrieval_record(),))
        self.assertEqual(resolution.status, "memory_unavailable")
        self.assertIsNone(resolution.context)

    def test_invalid_source_generation_id_returns_memory_unavailable(self):
        resolution = self._resolve_with_retrieval(
            self._retrieval_evidence(source_generation_id="not-a-canonical-uuid"),
            (self._retrieval_record(),))
        self.assertEqual(resolution.status, "memory_unavailable")
        self.assertIsNone(resolution.context)

    def test_valid_source_generation_mismatch_is_stale_source(self):
        resolution = self._resolve_with_retrieval(
            self._retrieval_evidence(source_generation_id=synthetic_uuid(0x50000000)),
            (self._retrieval_record(),),
            expected_generation_id=synthetic_uuid(0x60000000))
        self.assertEqual(resolution.status, "stale_source")
        self.assertIsNone(resolution.context)

    def test_non_string_record_content_fails_closed(self):
        resolution = self._resolve_with_retrieval(
            self._retrieval_evidence(source_generation_id=synthetic_uuid(0x50000000)),
            (self._retrieval_record(content=12345),))
        self.assertEqual(resolution.status, "context_validation_failed")
        self.assertIsNone(resolution.context)

    def test_invalid_request_does_not_retrieve_or_return_context(self):
        provider = SyntheticPersonalizedMemoryContextProvider(
            self.repository,
            context={"kind": "project"},
            relevance_keys=(),
            allowed_kinds=("preference",),
            limit=5)
        with patch.object(self.repository, "retrieve") as retrieve:
            resolution = provider.resolve()
        retrieve.assert_not_called()
        self.assertEqual(resolution.status, "invalid_request")
        self.assertIsNone(resolution.context)

    def test_repository_exception_returns_provider_error(self):
        with patch.object(self.repository, "retrieve",
                          side_effect=PersonalizedMemoryError("synthetic failure")):
            resolution = self.provider().resolve()
        self.assertEqual(resolution.status, "provider_error")
        self.assertIsNone(resolution.context)

    def test_resolution_is_a_typed_memory_context_resolution(self):
        self.create_approved()
        resolution = self.provider().resolve()
        self.assertIsInstance(resolution, MemoryContextResolution)


if __name__ == "__main__":
    unittest.main()
