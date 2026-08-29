"""Command-line entry point for one explicit local GRACI operator turn."""

import argparse
import json
from collections.abc import Callable, Sequence

from .operator_cli import build_operator_coordinator, serialize_turn_result
from .turn_coordinator import ExplicitTurnCoordinator, TurnDisposition
from .vertical_slice import VerticalSliceController


def main(argv: Sequence[str] | None = None, *,
         coordinator_factory: Callable[[], ExplicitTurnCoordinator] = build_operator_coordinator,
         input_fn: Callable[[str], str] = input) -> int:
    parser = argparse.ArgumentParser(description="Run one explicit local GRACI operator turn")
    parser.add_argument("task", nargs="?", help="text task to submit")
    parser.add_argument("--speech", action="store_true",
                        help="explicitly capture and transcribe one push-to-talk turn")
    parser.add_argument("--speak", action="store_true",
                        help="present the authoritative final response through local speech")
    parser.add_argument("--workspace", help="existing isolated workspace for a Phase 1C text action")
    parser.add_argument("--target", help="single allowed relative target path for a Phase 1C text action")
    args = parser.parse_args(argv)
    if bool(args.workspace) != bool(args.target):
        parser.error("--workspace and --target must be supplied together")
    if args.workspace:
        if args.speech or args.speak or args.task is None:
            parser.error("the specialized --workspace/--target path requires a typed task and no voice options")
        record = VerticalSliceController(args.workspace, args.target).run(args.task)
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0 if record["status"] == "PASS" else 1
    if args.speech == (args.task is not None):
        parser.error("provide exactly one typed task or --speech")

    coordinator = coordinator_factory()
    if args.speech:
        input_fn("Press Enter to begin push-to-talk capture.")
        result = coordinator.begin_speech_turn()
        if result is None:
            input_fn("Recording. Press Enter to stop and transcribe.")
            result = coordinator.finish_speech_turn(present_speech=args.speak)
    else:
        result = coordinator.run_typed(args.task, present_speech=args.speak)
    print(json.dumps(serialize_turn_result(result, speech_requested=args.speak),
                     indent=2, ensure_ascii=False))
    return 0 if result.disposition is TurnDisposition.GOVERNED_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
