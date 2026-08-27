"""Run the Phase 2B localhost-only governed multi-file validation."""
import json, tempfile
from pathlib import Path

from graci.autonomous import AutonomousRepairController, LoopLimits
from graci.config import Config

def main() -> int:
    phase = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="graci-phase2b-") as temporary:
        workspace = Path(temporary); (workspace / "tests").mkdir()
        (workspace / "invoice.py").write_text(
            "from settings import DISCOUNT\n\ndef final_price(subtotal):\n    return subtotal + DISCOUNT\n", encoding="utf-8")
        (workspace / "settings.py").write_text("DISCOUNT = 15\n", encoding="utf-8")
        (workspace / "tests" / "test_invoice.py").write_text(
            "import unittest\nfrom invoice import final_price\nfrom settings import DISCOUNT\n\nclass InvoiceTests(unittest.TestCase):\n"
            "    def test_discount_configuration(self):\n        self.assertEqual(DISCOUNT, 10)\n\n"
            "    def test_discount(self):\n        self.assertEqual(final_price(100), 90)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8")
        controller = AutonomousRepairController(workspace,
            readable_files=["invoice.py", "settings.py", "tests/test_invoice.py"],
            editable_files=["invoice.py", "settings.py"],
            limits=LoopLimits(max_iterations=12, max_model_calls=12, max_file_inspections=6,
                              max_file_modifications=4, max_repairs=2, command_timeout_seconds=30),
            config=Config(run_directory=phase / "evidence"))
        record = controller.run("Inspect this project, determine why its tests fail, repair all defects necessary for the test suite to pass, and verify the result.")
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0 if record["status"] == "PASS" and len(record["modified_paths"]) >= 2 else 1

if __name__ == "__main__": raise SystemExit(main())
