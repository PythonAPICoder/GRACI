"""Run the bounded final Phase 3E live acceptance from NOT_RUNNING state."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from graci.distributed import Phase3DDistributedRouter
from graci.registry import (
    GLM_MODEL_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID, HealthState,
    apply_health_result, build_phase3a_registry, check_openai_models_endpoint,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "phase3e" / "evidence"


def stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def persist(record):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    destination = EVIDENCE / f"{record['run_id']}.json"
    temporary = EVIDENCE / f".{record['run_id']}.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def main():
    started_at = stamp()
    registry = build_phase3a_registry()
    primary = registry.endpoints[PRIMARY_ENDPOINT_ID]
    primary_health = check_openai_models_endpoint(
        primary, timeout_seconds=5.0,
        expected_models=(QWEN_MODEL_ID, GLM_MODEL_ID))
    registry = registry.with_endpoint(apply_health_result(primary, primary_health))
    record = {
        "schema_version": 1, "phase": "3E-live",
        "run_id": str(uuid.uuid4()), "started_at": started_at, "ended_at": None,
        "expected_state": {"mo2": "NOT_RUNNING", "primary_healthy": True,
                           "optional_healthy": True,
                           "models": [QWEN_MODEL_ID, GLM_MODEL_ID]},
        "primary_health": {**primary_health.__dict__,
                           "state": primary_health.state.value,
                           "observed_models": list(primary_health.observed_models)},
        "local": None, "optional": None, "cloud_ai_used": False,
        "authoritative_repository_mutated_by_4090": False,
        "shared_storage_used": False, "status": "FAIL", "errors": [],
    }
    if primary_health.state != HealthState.HEALTHY:
        record["errors"].append("primary_3090_health_failed")
    else:
        router = Phase3DDistributedRouter(
            registry, run_directory=EVIDENCE, timeout_seconds=60.0)
        local = router.route(
            "general_reasoning",
            "Reply with the exact text GRACI_PHASE3E_LOCAL_OK and no additional text.")
        record["local"] = {
            "routing_evidence_run_id": local.evidence["run_id"],
            "node": local.node_id, "model": local.response_model,
            "content": local.content, "evidence": local.evidence,
        }
        optional = router.route(
            "implementer",
            "Reply with the exact text GRACI_PHASE3E_4090_OK and no additional text.",
            prefer_optional=True)
        record["optional"] = {
            "routing_evidence_run_id": optional.evidence["run_id"],
            "node": optional.node_id, "model": optional.response_model,
            "content": optional.content, "evidence": optional.evidence,
        }
        optional_gate = optional.evidence.get("eligibility") or {}
        observed = set((optional_gate.get("endpoint_health") or {}).get(
            "observed_models", []))
        passed = (
            local.node_id == "3090" and local.response_model == QWEN_MODEL_ID and
            local.evidence["contact_counts"] == {
                "4090_chat_completions": 0, "3090_chat_completions": 1} and
            optional.node_id == "4090" and optional.response_model == QWEN_MODEL_ID and
            optional_gate.get("eligible") is True and
            (optional_gate.get("mo2") or {}).get("state") == "NOT_RUNNING" and
            {QWEN_MODEL_ID, GLM_MODEL_ID}.issubset(observed) and
            optional.evidence["contact_counts"] == {
                "4090_chat_completions": 1, "3090_chat_completions": 0} and
            not local.evidence["cloud_ai_used"] and
            not optional.evidence["cloud_ai_used"])
        if passed:
            record["status"] = "PASS"
        else:
            record["errors"].append("live_expectation_mismatch")
    record["ended_at"] = stamp()
    destination = persist(record)
    print(json.dumps({"evidence": str(destination), "status": record["status"]}, indent=2))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
