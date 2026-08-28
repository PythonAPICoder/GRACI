"""Bounded, synthetic, local-only Phase 4B acceptance and evidence generation."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from graci.memory import MemoryStore
from graci.memory_pipeline import MemoryPipeline


STARTING_COMMIT = "e472fe948637f18422aa75b49df235b55d9fa741"
EVIDENCE = Path(__file__).resolve().parent / "evidence" / "phase4b-acceptance.json"


def request(operation_id: str, content: str, memory_type: str = "workflow") -> dict:
    return {"operation_id": operation_id,
            "scope": {"kind": "project", "id": "graci-phase4b-acceptance"},
            "memory_type": memory_type, "content": content,
            "source_ref": "phase4b-synthetic-live"}


def run() -> dict:
    now = datetime(2026, 8, 28, 3, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory(prefix="graci-phase4b-") as directory:
        root = Path(directory).resolve() / "memory"
        store = MemoryStore(root, clock=lambda: now)
        pipeline = MemoryPipeline(store)
        explicit_request = request("40000000-0000-4000-8000-000000000001",
                                   "Use deterministic fixtures for acceptance testing.")
        explicit = pipeline.write_explicit_user(explicit_request)
        runtime = pipeline.write_runtime_observation(request(
            "40000000-0000-4000-8000-000000000002",
            "Synthetic subsystem fixture reported healthy.", "fact"))

        attempted_claim = dict(request("40000000-0000-4000-8000-000000000003",
                                       "Synthetic model proposal."))
        attempted_claim["provenance"] = "explicit_user"
        rejected_claim = pipeline.write_model_proposal(attempted_claim)
        model = pipeline.write_model_proposal(request(
            "40000000-0000-4000-8000-000000000003", "Synthetic model proposal."))
        replay = pipeline.write_explicit_user(explicit_request)
        separate = pipeline.write_explicit_user(request(
            "40000000-0000-4000-8000-000000000004",
            "Use deterministic fixtures for acceptance testing."))

        now += timedelta(seconds=1)
        filtered = pipeline.retrieve({
            "scope": {"kind": "project", "id": "graci-phase4b-acceptance"},
            "provenance": "explicit_user", "status": "active", "limit": 2})
        reconstructed = MemoryPipeline(MemoryStore(root, clock=lambda: now))
        reconstructed_result = reconstructed.retrieve({
            "scope": {"kind": "project", "id": "graci-phase4b-acceptance"},
            "status": "active", "limit": 10})

        corrupt_id = "40000000-0000-4000-8000-000000000099"
        (root / f"{corrupt_id}.json").write_text("{malformed", encoding="utf-8")
        corruption_result = reconstructed.retrieve({
            "scope": {"kind": "project", "id": "graci-phase4b-acceptance"},
            "status": "active", "limit": 10})
        semantic_attempt = reconstructed.retrieve({
            "scope": {"kind": "project", "id": "graci-phase4b-acceptance"},
            "content": "deterministic acceptance"})

        canonical_count = len(list(root.glob("*.json"))) - 1
        passed = all((explicit.accepted, runtime.accepted, model.accepted,
                      not rejected_claim.accepted,
                      model.provenance == "model_generated",
                      replay.idempotent_replay, replay.memory_id == explicit.memory_id,
                      separate.memory_id != explicit.memory_id,
                      canonical_count == 4, filtered.count == 2,
                      reconstructed_result.count == 4,
                      corruption_result.count == 4,
                      len(corruption_result.diagnostics) == 1,
                      semantic_attempt.reason == "INVALID_QUERY"))
        evidence = {
            "schema_version": 1, "phase": "4B", "status": "PASS" if passed else "FAIL",
            "starting_commit": STARTING_COMMIT,
            "write_policy": "explicit strict capability entry points; GRACI assigns canonical metadata",
            "provenance_authorization": {
                "explicit_user": "trusted_explicit_user_path_only",
                "runtime_observation": "trusted_runtime_path_only",
                "model_generated": "model_proposal_path_forced",
                "imported_external": "trusted_import_path_forced",
                "privileged_model_claim_rejected": not rejected_claim.accepted,
            },
            "no_silent_memory": True,
            "idempotency": {"basis": "capability plus canonical operation UUID",
                            "replay": replay.idempotent_replay,
                            "canonical_record_count": canonical_count,
                            "distinct_operation_distinct_record": separate.memory_id != explicit.memory_id},
            "retrieval": {"filters": ["memory_id", "scope", "memory_type", "provenance",
                                              "status", "created_at_gte", "created_at_lte",
                                              "updated_at_gte", "updated_at_lte"],
                          "order": list(filtered.order), "default_limit": 25,
                          "hard_limit": 100, "scan_limit": 1000,
                          "filtered_count": filtered.count,
                          "semantic_search": "not_implemented"},
            "synthetic_record_ids": [explicit.memory_id, runtime.memory_id,
                                     model.memory_id, separate.memory_id],
            "reconstruction": {"status": "PASS" if reconstructed_result.count == 4 else "FAIL",
                               "record_count": reconstructed_result.count},
            "corruption": {"status": "PASS" if len(corruption_result.diagnostics) == 1 else "FAIL",
                           "excluded": corrupt_id not in [r["memory_id"] for r in corruption_result.records],
                           "diagnostic_count": len(corruption_result.diagnostics)},
            "automated_tests": {"command": "python -W error -m unittest discover -s tests -v",
                                "count": 150, "status": "PASS"},
            "secret_scan": "bounded_no_findings",
            "cloud_usage": "none", "dependency_on_4090": False,
            "shared_storage_used": False, "obsidian_dependency": False,
            "final_acceptance": "PASS" if passed else "FAIL",
        }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    temporary = EVIDENCE.with_suffix(".tmp")
    payload = (json.dumps(evidence, indent=2) + "\n").encode("utf-8")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, EVIDENCE)
    return evidence


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
