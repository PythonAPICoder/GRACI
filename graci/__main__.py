"""Command-line entry point for one explicit local GRACI operator turn."""

import argparse
import json
import sys
from collections.abc import Callable, Sequence

from .keyboard_input import HoldSpacebarToTalk, KeyboardInput, WindowsSpacebarInput
from .operator_cli import (OperatorComposition, build_operator_composition,
                           build_operator_coordinator, serialize_turn_result)
from .turn_coordinator import ExplicitTurnCoordinator, TurnDisposition
from .vertical_slice import VerticalSliceController


def main(argv: Sequence[str] | None = None, *,
         coordinator_factory: Callable[[], ExplicitTurnCoordinator] = build_operator_coordinator,
         composition_factory: Callable[..., OperatorComposition] = build_operator_composition,
         input_fn: Callable[[str], str] = input,
         keyboard_factory: Callable[[], KeyboardInput] = WindowsSpacebarInput,
         prompt_fn: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="Run one explicit local GRACI operator turn")
    parser.add_argument("task", nargs="?", help="text task to submit")
    parser.add_argument("--speech", action="store_true",
                        help="hold Spacebar for one capture; release to transcribe")
    parser.add_argument("--speak", action="store_true",
                        help="present the authoritative final response through local speech")
    parser.add_argument("--visualizer", action="store_true",
                        help="serve the observer-only browser visualizer on 127.0.0.1:8766")
    parser.add_argument("--visualizer-hold", action="store_true",
                        help="keep the enabled visualizer open until Enter after the turn")
    parser.add_argument("--workspace", help="existing isolated workspace for a Phase 1C text action")
    parser.add_argument("--target", help="single allowed relative target path for a Phase 1C text action")
    args = parser.parse_args(argv)
    if args.visualizer_hold and not args.visualizer:
        parser.error("--visualizer-hold requires --visualizer")
    if bool(args.workspace) != bool(args.target):
        parser.error("--workspace and --target must be supplied together")
    if args.workspace:
        if args.speech or args.speak or args.visualizer or args.task is None:
            parser.error("the specialized --workspace/--target path requires a typed task and no voice options")
        record = VerticalSliceController(args.workspace, args.target).run(args.task)
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0 if record["status"] == "PASS" else 1
    if args.speech == (args.task is not None):
        parser.error("provide exactly one typed task or --speech")

    composition = composition_factory(visualizer=True) if args.visualizer else None
    coordinator = (composition.coordinator if composition is not None
                   else coordinator_factory())
    server = composition.server if composition is not None else None
    if server is not None:
        server.start()
        print(f"Observer-only visualizer: http://127.0.0.1:{server.bound_port}/",
              file=sys.stderr)
    try:
        if args.speech:
            prompt_fn("Hold Spacebar to talk; release Spacebar to stop and transcribe.")
            result = HoldSpacebarToTalk(keyboard_factory()).run(
                coordinator, present_speech=args.speak)
        else:
            result = coordinator.run_typed(args.task, present_speech=args.speak)
        if args.visualizer_hold:
            input_fn("Visualizer is live. Press Enter to close it.")
    finally:
        if server is not None:
            server.stop()
    print(json.dumps(serialize_turn_result(result, speech_requested=args.speak),
                     indent=2, ensure_ascii=False))
    return 0 if result.disposition is TurnDisposition.GOVERNED_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
