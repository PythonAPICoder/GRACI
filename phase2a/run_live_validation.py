"""Run the Phase 2A live localhost-only autonomous repair validation."""

import json
import tempfile
from pathlib import Path

from graci.autonomous import AutonomousRepairController, LoopLimits
from graci.config import Config


def main() -> int:
    phase_directory = Path(__file__).resolve().parent
    evidence_directory = phase_directory / "evidence"
    with tempfile.TemporaryDirectory(prefix="graci-phase2a-") as temporary:
        workspace = Path(temporary)
        (workspace / "tests").mkdir()
        (workspace / "calculator.py").write_text(
            "def add(left, right):\n    return left - right\n", encoding="utf-8")
        (workspace / "tests" / "test_calculator.py").write_text(
            "import unittest\nfrom calculator import add\n\n"
            "class CalculatorTests(unittest.TestCase):\n"
            "    def test_adds_positive_numbers(self):\n"
            "        self.assertEqual(add(7, 5), 12)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n",
            encoding="utf-8")
        controller = AutonomousRepairController(
            workspace,
            readable_files=["calculator.py", "tests/test_calculator.py"],
            editable_files=["calculator.py"],
            limits=LoopLimits(max_iterations=8, max_repairs=2, command_timeout_seconds=30),
            config=Config(run_directory=evidence_directory),
        )
        record = controller.run(
            "Inspect this project, determine why its tests fail, repair the defect, "
            "and verify the tests pass."
        )
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
