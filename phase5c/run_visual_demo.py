"""Run the localhost visualizer with a looping trusted synthetic lifecycle."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graci.visualizer import SystemState
from graci.visualizer_backend import DEFAULT_PORT, VisualizerServer, VisualizerStateProvider
from phase5c.synthetic import lifecycle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hold", choices=tuple(state.value for state in SystemState) + ("blocked",))
    parser.add_argument("--interval", type=float, default=2.5)
    args = parser.parse_args()
    provider = VisualizerStateProvider()
    snapshots, events = lifecycle(blocked_4090=args.hold == "blocked")
    if args.hold:
        desired = "reasoning" if args.hold == "blocked" else args.hold
        selected = next(item for item in snapshots if item.system_state.value == desired)
        provider.publish_snapshot(selected)
        for event in events[:5]: provider.publish_event(event, observed_at=events[-1].timestamp)
    with VisualizerServer(provider):
        print(f"G.R.A.C.I. Phase 5C visual demo: http://127.0.0.1:{DEFAULT_PORT}/", flush=True)
        try:
            if args.hold:
                while True: time.sleep(1)
            while True:
                for index, snapshot in enumerate(snapshots):
                    provider.publish_snapshot(snapshot)
                    if index < len(events):
                        provider.publish_event(events[index], observed_at=events[-1].timestamp)
                    time.sleep(max(.25, args.interval))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
