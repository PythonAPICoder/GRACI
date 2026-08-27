"""Run the Phase 1D live localhost-only integrated acceptance scenario."""

import json
from pathlib import Path

from graci.config import Config
from graci.vertical_slice import VerticalSliceController


def main() -> int:
    phase_directory = Path(__file__).resolve().parent
    workspace = phase_directory / "live-sandbox"
    evidence = phase_directory / "evidence"
    controller = VerticalSliceController(
        workspace,
        "phase1-accepted.txt",
        config=Config(run_directory=evidence),
    )
    record = controller.run(
        "Create or update phase1-accepted.txt so its contents exactly match this text, "
        "with no added newline: GRACI Phase 1 live acceptance verified"
    )
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
