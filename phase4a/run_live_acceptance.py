"""Bounded local-only Phase 4A storage acceptance and evidence generation."""

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from graci.memory import MemoryStore, MemoryValidationError


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "phase4a" / "live-memory-fixture"
EVIDENCE = ROOT / "phase4a" / "evidence"


def stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def persist(record):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    destination = EVIDENCE / "phase4a-acceptance.json"
    temporary = EVIDENCE / ".phase4a-acceptance.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def main():
    shutil.rmtree(FIXTURE, ignore_errors=True)
    record = {"schema_version": 1, "phase": "4A", "started_at": stamp(),
              "ended_at": None, "storage_type": "canonical_utf8_json_per_uuid",
              "memory_root_semantics": "host-selected authoritative 3090 local directory",
              "created_record_ids": [], "persistence_reconstruction": "FAIL",
              "enumeration": None, "controlled_update": "FAIL",
              "corruption_test": "FAIL", "filesystem_boundary": "FAIL",
              "atomicity": "same-directory fsync temporary; no-overwrite hard-link create; os.replace update",
              "automated_tests": "recorded after full suite",
              "cloud_network_usage": "none", "shared_storage_used": False,
              "dependency_on_4090": False, "status": "FAIL", "errors": []}
    try:
        store = MemoryStore(FIXTURE.resolve())
        first = store.create(store.new_record(
            memory_id="44444444-4444-4444-8444-444444444441",
            scope={"kind": "project", "id": "graci-phase4a"}, memory_type="decision",
            content="Canonical structured memory is authoritative storage.",
            provenance={"origin": "explicit_user", "source_ref": "phase4a-acceptance"}))
        second = store.create(store.new_record(
            memory_id="44444444-4444-4444-8444-444444444442",
            scope={"kind": "global", "id": None}, memory_type="context",
            content="Instruction-like memory is stored only as untrusted data.",
            provenance={"origin": "runtime_observation", "source_ref": "phase4a-acceptance"}))
        record["created_record_ids"] = [first["memory_id"], second["memory_id"]]
        rebuilt = MemoryStore(FIXTURE.resolve())
        if rebuilt.get(first["memory_id"]) == first and rebuilt.get(second["memory_id"]) == second:
            record["persistence_reconstruction"] = "PASS"
        listing = rebuilt.enumerate(limit=10)
        record["enumeration"] = {"ids": [item["memory_id"] for item in listing.records],
                                 "deterministic": [item["memory_id"] for item in listing.records]
                                 == sorted(record["created_record_ids"]), "bounded_limit": 10}
        updated = rebuilt.update(first["memory_id"], content="Canonical JSON remains durable data.")
        if updated["version"] == 2 and updated["memory_id"] == first["memory_id"]:
            record["controlled_update"] = "PASS"
        corrupt_id = "44444444-4444-4444-8444-444444444443"
        (FIXTURE / f"{corrupt_id}.json").write_text('{"truncated":', encoding="utf-8")
        diagnostics = rebuilt.enumerate(limit=10)
        if corrupt_id not in [item["memory_id"] for item in diagnostics.records] and diagnostics.corruptions:
            record["corruption_test"] = "PASS"
        try:
            rebuilt.get("../PROJECT_STATE")
        except MemoryValidationError:
            record["filesystem_boundary"] = "PASS"
        passed = (record["persistence_reconstruction"] == "PASS" and
                  record["enumeration"]["deterministic"] and
                  record["controlled_update"] == "PASS" and
                  record["corruption_test"] == "PASS" and
                  record["filesystem_boundary"] == "PASS")
        record["status"] = "PASS" if passed else "FAIL"
    except Exception as exc:
        record["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(FIXTURE, ignore_errors=True)
    record["ended_at"] = stamp()
    destination = persist(record)
    print(json.dumps({"evidence": str(destination), "status": record["status"]}, indent=2))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
