"""Optional console smoke test; not part of automated acceptance."""

from __future__ import annotations

import argparse
from pathlib import Path

from graci.audio_capture import AudioCaptureConfig, WindowsWaveInCapture
from graci.push_to_talk import PushToTalkController
from graci.speech import FasterWhisperConfig, FasterWhisperSubprocessSTT


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicit local GRACI push-to-talk smoke test")
    parser.add_argument("--python", type=Path, default=ROOT / "phase6a/.venv/Scripts/python.exe")
    parser.add_argument("--device-id", type=int, default=-1)
    parser.add_argument("--retain-audio", action="store_true")
    args = parser.parse_args()
    retained = ROOT / "phase6b/debug-audio" if args.retain_audio else None
    stt = FasterWhisperSubprocessSTT(FasterWhisperConfig(
        python_executable=args.python,
        worker_script=ROOT / "phase6b/stt_worker.py",
        model_cache=ROOT / "phase6a/cache/huggingface",
        retain_audio=args.retain_audio,
        retained_audio_directory=retained,
    ))
    controller = PushToTalkController(
        WindowsWaveInCapture(), stt, AudioCaptureConfig(device_id=args.device_id))
    input("Press Enter to BEGIN recording; microphone is idle until then.")
    controller.begin()
    input("Recording. Press Enter to STOP and transcribe locally.")
    result = controller.end_and_transcribe()
    print(result)


if __name__ == "__main__":
    main()
