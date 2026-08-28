"""Run the bounded Phase 3B local Qwen/GLM acceptance fixture."""

import json
import tempfile
from pathlib import Path

from graci.phase3b import Phase3BController
from graci.registry import (GLM_MODEL_ID, PRIMARY_ENDPOINT_ID, QWEN_MODEL_ID,
                            apply_health_result, build_phase3a_registry,
                            check_openai_models_endpoint)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "phase3b" / "evidence"


def main() -> int:
    registry = build_phase3a_registry()
    endpoint = registry.endpoints[PRIMARY_ENDPOINT_ID]
    health = check_openai_models_endpoint(
        endpoint, timeout_seconds=5.0, expected_models=(QWEN_MODEL_ID, GLM_MODEL_ID))
    registry = registry.with_endpoint(apply_health_result(endpoint, health))
    if health.state.value != "healthy":
        print(json.dumps({"status": "FAIL", "health": health.__dict__}, indent=2))
        return 1
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="graci-phase3b-") as temporary:
        workspace = Path(temporary)
        (workspace / "tests").mkdir()
        (workspace / "discount.py").write_text(
            "def discounted_price(price: float, percent: float) -> float:\n"
            "    return price + (price * percent / 100)\n", encoding="utf-8")
        (workspace / "tests" / "test_discount.py").write_text(
            "import unittest\nfrom discount import discounted_price\n\n"
            "class DiscountTests(unittest.TestCase):\n"
            "    def test_twenty_percent(self):\n"
            "        self.assertEqual(discounted_price(100, 20), 80)\n\n"
            "    def test_zero_percent(self):\n"
            "        self.assertEqual(discounted_price(50, 0), 50)\n", encoding="utf-8")
        controller = Phase3BController(
            workspace, registry=registry,
            readable_files=("discount.py", "tests/test_discount.py"),
            editable_files=("discount.py",), test_directory="tests",
            run_directory=EVIDENCE)
        record = controller.run(
            "Repair discount.py so discounted_price subtracts the supplied percentage. "
            "Inspect the bounded files as needed, replace only discount.py, and run the tests.")
    record["live_endpoint_health"] = {
        "state": health.state.value, "reason": health.reason,
        "checked_at": health.checked_at, "observed_models": list(health.observed_models),
        "http_status": health.http_status}
    controller._persist(record)
    print(json.dumps({"run_id": record["run_id"], "status": record["status"],
                      "review": record["review"]["invocation_status"],
                      "verdict": record["review"]["verdict"],
                      "adjudication": record["adjudication"]["result"]}, indent=2))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
