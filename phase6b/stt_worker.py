"""Bounded JSON worker for the local faster-whisper adapter."""

from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--device", choices=("cpu",), required=True)
    parser.add_argument("--compute-type", choices=("int8",), required=True)
    args = parser.parse_args()
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type,
                         download_root=args.cache, local_files_only=True)
    segments, info = model.transcribe(args.audio, language="en", beam_size=5,
                                      vad_filter=False, condition_on_previous_text=False)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    print(json.dumps({"text": text, "language": info.language,
                      "language_probability": info.language_probability}))


if __name__ == "__main__":
    main()
