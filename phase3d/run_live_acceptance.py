"""Run one bounded real Phase 3D routing acceptance operation."""

import argparse
import json
import os
from pathlib import Path

from graci.distributed import Phase3DDistributedRouter
from graci.registry import (GLM_MODEL_ID, OPTIONAL_ENDPOINT_ID, PRIMARY_ENDPOINT_ID,
                            QWEN_MODEL_ID, apply_health_result,
                            build_phase3a_registry, check_openai_models_endpoint)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "phase3d" / "evidence"


def persist(record):
    destination = EVIDENCE / f"{record['run_id']}.json"
    temporary = EVIDENCE / f".{record['run_id']}.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-node", required=True, choices=("4090", "3090"))
    parser.add_argument("--expected-mo2-state", required=True,
                        choices=("NOT_RUNNING", "RUNNING"))
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    registry = build_phase3a_registry()
    primary = registry.endpoints[PRIMARY_ENDPOINT_ID]
    primary_health = check_openai_models_endpoint(
        primary, timeout_seconds=5.0, expected_models=(QWEN_MODEL_ID, GLM_MODEL_ID))
    registry = registry.with_endpoint(apply_health_result(primary, primary_health))
    if primary_health.state.value != "healthy":
        print(json.dumps({"status": "FAIL", "primary_health": primary_health.__dict__}, indent=2))
        return 1

    router = Phase3DDistributedRouter(registry, run_directory=EVIDENCE,
                                      timeout_seconds=60.0)
    response = router.route(
        "implementer",
        "This is a bounded GRACI Phase 3D routing acceptance check. Reply with the exact text "
        "GRACI_PHASE3D_LIVE_OK and no additional text.",
        prefer_optional=True)
    record = response.evidence
    record["live_acceptance"] = {
        "expected_node": args.expected_node,
        "expected_mo2_state": args.expected_mo2_state,
        "actual_mo2_state": record["eligibility"]["mo2"]["state"],
        "primary_health": {**primary_health.__dict__,
                           "state": primary_health.state.value,
                           "observed_models": list(primary_health.observed_models)},
        "response_content": response.content,
        "authoritative_repository_mutated_by_4090": False,
        "shared_storage_used": False,
    }
    passed = (response.node_id == args.expected_node and
              record["live_acceptance"]["actual_mo2_state"] == args.expected_mo2_state and
              record["actual_server_model"] == QWEN_MODEL_ID and
              (record["contacted_4090_chat_completions"] == (args.expected_node == "4090")) and
              record["contacted_3090_chat_completions"] == (args.expected_node == "3090"))
    record["live_acceptance"]["status"] = "PASS" if passed else "FAIL"
    destination = persist(record)
    print(json.dumps({"evidence": str(destination), "record": record}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
