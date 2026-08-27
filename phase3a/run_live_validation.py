"""Validate only the local 3090 registry endpoint and persist factual evidence."""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from graci.registry import (GLM_MODEL_ID, OPTIONAL_ENDPOINT_ID, OPTIONAL_NODE_ID,
                            PRIMARY_ENDPOINT_ID, PRIMARY_NODE_ID, QWEN_MODEL_ID,
                            REGISTRY_SCHEMA_VERSION, apply_health_result,
                            build_phase3a_registry, check_openai_models_endpoint,
                            evaluate_eligibility)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    registry = build_phase3a_registry()
    health = check_openai_models_endpoint(
        registry.endpoints[PRIMARY_ENDPOINT_ID], timeout_seconds=5.0,
        expected_models=(QWEN_MODEL_ID,))
    registry = registry.with_endpoint(
        apply_health_result(registry.endpoints[PRIMARY_ENDPOINT_ID], health))
    primary = evaluate_eligibility(registry, PRIMARY_NODE_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID)
    optional = evaluate_eligibility(registry, OPTIONAL_NODE_ID, OPTIONAL_ENDPOINT_ID, QWEN_MODEL_ID)
    glm_advertised = GLM_MODEL_ID in health.observed_models
    passed = health.state.value == "healthy" and primary.eligible and not optional.eligible
    record = {
        "schema_version": 1, "registry_schema_version": REGISTRY_SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()), "timestamp": timestamp(),
        "nodes_represented": sorted(registry.nodes),
        "live_requests": [registry.endpoints[PRIMARY_ENDPOINT_ID].base_url + "/models"],
        "primary_health": {"state": health.state.value, "reason": health.reason,
                           "http_status": health.http_status,
                           "checked_at": health.checked_at},
        "models_observed": list(health.observed_models),
        "expected_models": {QWEN_MODEL_ID: QWEN_MODEL_ID in health.observed_models,
                            GLM_MODEL_ID: glm_advertised},
        "primary_eligibility": {"eligible": primary.eligible,
                                "reason_code": primary.reason_code.value,
                                "explanation": primary.explanation},
        "optional_4090_eligibility": {"eligible": optional.eligible,
                                      "reason_code": optional.reason_code.value,
                                      "explanation": optional.explanation,
                                      "live_checked": False},
        "status": "PASS" if passed else "FAIL",
    }
    evidence = Path(__file__).resolve().parent / "evidence"
    evidence.mkdir(exist_ok=True)
    destination = evidence / f"{record['run_id']}.json"
    temporary = evidence / f".{record['run_id']}.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    print(json.dumps(record, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
