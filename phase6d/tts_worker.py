"""Strict one-shot local Kokoro-82M ONNX synthesis worker."""

from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--voices", type=Path, required=True)
    parser.add_argument("--voice", choices=("af_bella",), required=True)
    parser.add_argument("--device", choices=("cpu",), required=True)
    parser.add_argument("--max-text-chars", type=int, required=True)
    parser.add_argument("--max-audio-bytes", type=int, required=True)
    parser.add_argument("--max-audio-seconds", type=float, required=True)
    args = parser.parse_args()
    text = args.text_file.read_text(encoding="utf-8")
    if not text.strip() or len(text) > args.max_text_chars:
        raise ValueError("speech presentation text is blank or exceeds its bound")
    if not args.model.is_file() or not args.voices.is_file():
        raise FileNotFoundError("local Kokoro model or voices asset is unavailable")
    from kokoro_onnx import Kokoro
    import soundfile as sf
    pipeline = Kokoro(str(args.model), str(args.voices))
    audio, sample_rate = pipeline.create(text, voice=args.voice, speed=1.0, lang="en-us")
    duration = len(audio) / sample_rate
    if duration <= 0 or duration > args.max_audio_seconds:
        raise ValueError("generated audio duration is out of bounds")
    sf.write(args.output, audio, sample_rate, subtype="PCM_16", format="WAV")
    if args.output.stat().st_size > args.max_audio_bytes:
        args.output.unlink(missing_ok=True)
        raise ValueError("generated audio exceeds the byte bound")
    with wave.open(str(args.output), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError("generated audio must be mono 16-bit PCM")
    print(json.dumps({"status": "success", "voice": args.voice, "device": args.device}))


if __name__ == "__main__":
    main()
