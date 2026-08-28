from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import soundfile as sf
from kokoro_onnx import Kokoro

from pronunciation import TECHNICAL_PRONUNCIATIONS, speech_presentation_text

SOURCE_LINES = (
    "GRACI will continue using the 3090.",
    "The 4090 is available for optional processing.",
    "The 4090 is unavailable, so GRACI will continue using the 3090.",
    "GRACI is running on the 3090, with the 4090 available as optional capacity.",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--voices", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    tts = Kokoro(args.model, args.voices)
    results = []
    for index, source_text in enumerate(SOURCE_LINES, 1):
        speech_text = speech_presentation_text(source_text)
        started = time.perf_counter()
        audio, sample_rate = tts.create(speech_text, voice="af_bella", speed=1.0, lang="en-us")
        output = args.output / f"technical-pronunciation-{index:02d}.wav"
        sf.write(output, audio, sample_rate)
        results.append({
            "line": index,
            "authoritative_source_text": source_text,
            "speech_presentation_text": speech_text,
            "file": output.as_posix(),
            "audio_seconds": round(len(audio) / sample_rate, 3),
            "generation_seconds": round(time.perf_counter() - started, 3),
        })
    evidence = {
        "schema_version": 1,
        "engine": "Kokoro-82M ONNX",
        "voice": "af_bella",
        "purpose": "Phase 6A explicit technical pronunciation QA",
        "authoritative_text_mutated": False,
        "explicit_pronunciations": dict(TECHNICAL_PRONUNCIATIONS),
        "generic_number_rewriting": False,
        "results": results,
    }
    (args.output / "technical-pronunciation-qa.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
