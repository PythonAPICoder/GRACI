"""Bounded JSON worker for the local faster-whisper adapter."""

from __future__ import annotations

import argparse
import json
import sys


def transcribe(model, audio: str) -> dict[str, object]:
    segments, info = model.transcribe(audio, language="en", beam_size=5,
                                      vad_filter=False,
                                      condition_on_previous_text=False)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    return {"text": text, "language": info.language,
            "language_probability": info.language_probability}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--model", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--device", choices=("cpu",), required=True)
    parser.add_argument("--compute-type", choices=("int8",), required=True)
    args = parser.parse_args()
    if args.serve == (args.audio is not None):
        parser.error("exactly one of --audio or --serve is required")
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type,
                         download_root=args.cache, local_files_only=True)
    if args.audio is not None:
        print(json.dumps(transcribe(model, args.audio)))
        return
    print(json.dumps({"status": "ready"}), flush=True)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            audio = request["audio"]
            if not isinstance(audio, str) or not audio:
                raise ValueError("audio path is required")
            response = transcribe(model, audio)
        except Exception as exc:
            response = {"error": str(exc)[:500]}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
