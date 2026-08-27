"""Command-line entry point: python -m graci TASK."""

import argparse
import json

from .controller import Controller


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a text task through the Phase 1A local controller")
    parser.add_argument("task", help="text task to submit")
    args = parser.parse_args()
    record = Controller().run(args.task)
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
