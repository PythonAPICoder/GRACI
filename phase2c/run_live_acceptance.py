"""Run the Phase 2C localhost-only integrated acceptance fixture."""
import json
import tempfile
from pathlib import Path

from graci.autonomous import AutonomousRepairController, LoopLimits
from graci.config import Config


def main() -> int:
    phase = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="graci-phase2c-") as temporary:
        workspace = Path(temporary)
        (workspace / "tests").mkdir()
        (workspace / "pricing.py").write_text(
            "from policy import DISCOUNT_RATE\n\ndef final_price(subtotal):\n"
            "    return subtotal + (subtotal * DISCOUNT_RATE)\n", encoding="utf-8")
        (workspace / "policy.py").write_text("DISCOUNT_RATE = 20\n", encoding="utf-8")
        (workspace / "tests" / "test_pricing.py").write_text(
            "import unittest\nfrom policy import DISCOUNT_RATE\nfrom pricing import final_price\n\n"
            "class PricingTests(unittest.TestCase):\n"
            "    def test_rate_is_fraction(self):\n        self.assertEqual(DISCOUNT_RATE, 0.20)\n\n"
            "    def test_discount_is_applied(self):\n        self.assertEqual(final_price(100), 80)\n",
            encoding="utf-8")
        controller = AutonomousRepairController(
            workspace,
            readable_files=["pricing.py", "policy.py", "tests/test_pricing.py"],
            editable_files=["pricing.py", "policy.py"], test_directory="tests",
            limits=LoopLimits(max_iterations=12, max_model_calls=12, max_file_inspections=6,
                              max_file_modifications=4, max_repairs=2,
                              command_timeout_seconds=30),
            config=Config(run_directory=phase / "evidence"))
        record = controller.run(
            "Inspect all relevant files and repair the related discount implementation and "
            "configuration defects. Both editable files require correction. Run the deterministic "
            "tests and finish only when they pass.")
        print(json.dumps(record, indent=2, ensure_ascii=False))
        accepted = (record["status"] == "PASS" and
                    set(record["inspected_paths"]) >= {"pricing.py", "policy.py", "tests/test_pricing.py"} and
                    set(record["modified_paths"]) >= {"pricing.py", "policy.py"} and
                    record["deterministic_verification"]["status"] == "PASS")
        return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
