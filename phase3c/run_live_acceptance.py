"""Capture one real Phase 3C 4090 state without performing inference."""

import argparse
import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from graci.availability import (
    Mo2State, Phase3CEligibilityReason, check_4090_mo2_status,
    evaluate_4090_eligibility,
)
from graci.registry import (
    OPTIONAL_ENDPOINT_ID, OPTIONAL_NODE_ID, QWEN_MODEL_ID,
    apply_health_result, build_phase3a_registry, check_openai_models_endpoint,
)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-state", required=True,
                        choices=(Mo2State.NOT_RUNNING.value, Mo2State.RUNNING.value))
    arguments = parser.parse_args()
    started_at = timestamp()
    run_id = str(uuid.uuid4())
    registry = build_phase3a_registry()
    endpoint = registry.endpoints[OPTIONAL_ENDPOINT_ID]

    mo2 = check_4090_mo2_status(timeout_seconds=5.0)
    health = check_openai_models_endpoint(endpoint, timeout_seconds=5.0)
    registry = registry.with_endpoint(apply_health_result(endpoint, health))
    eligibility = evaluate_4090_eligibility(registry, QWEN_MODEL_ID, mo2)

    expected_eligible = arguments.expected_state == Mo2State.NOT_RUNNING.value
    expected_reason = (Phase3CEligibilityReason.ELIGIBLE if expected_eligible else
                       Phase3CEligibilityReason.MO2_RUNNING)
    passed = (mo2.state.value == arguments.expected_state and
              health.state.value == "healthy" and
              QWEN_MODEL_ID in health.observed_models and
              eligibility.eligible == expected_eligible and
              eligibility.reason_code == expected_reason)
    record = {
        "schema_version": 1,
        "phase": "3C",
        "run_id": run_id,
        "started_at": started_at,
        "ended_at": timestamp(),
        "node_id": OPTIONAL_NODE_ID,
        "endpoint_id": OPTIONAL_ENDPOINT_ID,
        "endpoint": endpoint.base_url,
        "mo2_query": {
            **asdict(mo2),
            "state": mo2.state.value,
            "process_name": "ModOrganizer.exe",
            "expected_state": arguments.expected_state,
        },
        "endpoint_health": {
            **asdict(health),
            "state": health.state.value,
            "observed_models": list(health.observed_models),
        },
        "required_model_check": {
            "model_id": QWEN_MODEL_ID,
            "available": QWEN_MODEL_ID in health.observed_models,
        },
        "eligibility": {
            "eligible": eligibility.eligible,
            "reason_code": eligibility.reason_code.value,
            "explanation": eligibility.explanation,
        },
        "network_operations": [
            {"method": "GET", "purpose": "exact MO2 status",
             "path": "/graci/v1/mo2"},
            {"method": "GET", "purpose": "llama.cpp health and model discovery",
             "path": "/v1/models"},
        ],
        "inference_requests": 0,
        "cloud_ai_used": False,
        "final_status": "PASS" if passed else "FAIL",
    }
    evidence_directory = Path(__file__).resolve().parent / "evidence"
    evidence_directory.mkdir(parents=True, exist_ok=True)
    destination = evidence_directory / f"{run_id}.json"
    temporary = evidence_directory / f".{run_id}.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    print(json.dumps({"evidence": str(destination), "record": record}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
