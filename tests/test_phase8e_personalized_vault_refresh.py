"""Maintainer-only synthetic Phase 8E vault refresh tests."""

import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from graci.personalized_memory import (ExactApproval, ProposalRequest,
                                       SyntheticPersonalizedMemoryRepository)
from phase8e.personalized_projection import build_personalized_projection_request
from phase8e.personalized_vault_refresh import refresh_synthetic_vault
from phase8e.projection import (AuthorityClass, ProjectionError, RepositorySource,
                                ReviewClassification, SourceType, ProjectionVerifier)


ROOT = Path(__file__).resolve().parents[1]


def synthetic_uuid(number: int) -> str:
    return f"{number:08x}-0000-4000-8000-{number:012x}"


class PersonalizedVaultRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        generation_ids = iter(synthetic_uuid(0x81000000 + index) for index in range(100))
        self.repository = SyntheticPersonalizedMemoryRepository.initialize(
            self.root / "memory-state",
            clock=lambda: datetime(2026, 9, 2, 19, 0, tzinfo=timezone.utc),
            generation_id_factory=lambda: next(generation_ids),
        )
        self.counter = 1
        self.commit = subprocess.run(
            ("git", "-C", str(ROOT), "rev-parse", "HEAD"), check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        self.catalog = (RepositorySource(
            "docs/PRODUCT.md", "current/product.md", SourceType.CURRENT_STATE,
            ReviewClassification.PRODUCT_OWNER_REVIEW,
            AuthorityClass.DESCRIPTIVE_CURRENT_SOURCE,
        ),)

    def tearDown(self):
        self.temp.cleanup()

    def create_approved(self, content="Synthetic refresh fixture."):
        number = self.counter
        self.counter += 1
        operation_id = synthetic_uuid(0x10000000 + number)
        proposal = self.repository.propose(ProposalRequest(
            operation_id=operation_id, action="create",
            personalized_kind="working_method",
            scope={"kind": "project", "id": "synthetic-project"},
            relevance_key="workflow.synthetic.refresh", content=content,
            source_ref=f"synthetic:turn:{operation_id}",
            source_turn_id=synthetic_uuid(0x20000000 + number),
            proposal_origin="product_owner_direct", source_boundary="typed_turn"))
        self.assertTrue(proposal.accepted)
        stored = self.repository.read_proposal(proposal.proposal_id)
        approval = self.repository.approve(ExactApproval(
            operation_id=synthetic_uuid(0x30000000 + number),
            proposal_id=proposal.proposal_id,
            proposal_digest=stored["proposal_digest"],
            source_turn_id=synthetic_uuid(0x40000000 + number),
            channel="typed_turn"))
        self.assertTrue(approval.accepted)
        return approval

    def test_exact_synthetic_refresh_promotes_and_verifies_one_vault_generation(self):
        approval = self.create_approved()
        memory_generation_id = self.repository.current_snapshot().generation_id
        vault_generation_id = synthetic_uuid(0x90000001)
        result = refresh_synthetic_vault(
            repository=self.repository,
            memory_generation_id=memory_generation_id,
            vault_generation_id=vault_generation_id,
            repository_root=ROOT,
            source_commit=self.commit,
            catalog=self.catalog,
            staging_root=self.root / "staging",
            projection_root=self.root / "vault",
        )
        self.assertEqual(result["memory_generation_id"], memory_generation_id)
        self.assertEqual(result["vault_generation_id"], vault_generation_id)
        manifest = ProjectionVerifier(self.root / "vault").verify_current()
        self.assertEqual(manifest["generation_id"], vault_generation_id)
        note = (result["generation"] / "memory" / f"{approval.memory_id}.md").read_text("utf-8")
        self.assertIn("UNTRUSTED CONTEXT", note)
        self.assertIn("Synthetic refresh fixture.", note)

    def test_refresh_rejects_a_memory_request_from_a_different_generation(self):
        self.create_approved("First synthetic record.")
        first_generation = self.repository.current_snapshot().generation_id
        self.create_approved("Second synthetic record.")
        current_request = build_personalized_projection_request(
            self.repository, generation_id=self.repository.current_snapshot().generation_id)
        with self.assertRaisesRegex(ProjectionError, "synthetic root"):
            refresh_synthetic_vault(
                repository=self.repository,
                memory_generation_id=first_generation,
                vault_generation_id=synthetic_uuid(0x90000002),
                repository_root=ROOT,
                source_commit=self.commit,
                catalog=self.catalog,
                staging_root=self.root / "staging",
                projection_root=self.root / "vault",
                memory_request=current_request,
            )


if __name__ == "__main__":
    unittest.main()
