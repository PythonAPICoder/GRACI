"""One-shot blocking Windows WAV playback worker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("Phase 6D playback requires Windows")
    if not args.audio.is_file():
        raise FileNotFoundError("playback WAV is unavailable")
    import winsound
    winsound.PlaySound(str(args.audio), winsound.SND_FILENAME)


if __name__ == "__main__":
    main()
