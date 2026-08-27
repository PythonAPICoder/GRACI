"""Command-line entry point: python -m graci TASK."""

import argparse
import json

from .controller import Controller
from .vertical_slice import VerticalSliceController


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a text task through the GRACI local controller")
    parser.add_argument("task", help="text task to submit")
    parser.add_argument("--workspace", help="existing isolated workspace for a Phase 1C text action")
    parser.add_argument("--target", help="single allowed relative target path for a Phase 1C text action")
    args = parser.parse_args()
    if bool(args.workspace) != bool(args.target):
        parser.error("--workspace and --target must be supplied together")
    record = (VerticalSliceController(args.workspace, args.target).run(args.task)
              if args.workspace else Controller().run(args.task))
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
