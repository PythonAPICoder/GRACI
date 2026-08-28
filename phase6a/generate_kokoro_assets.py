from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import psutil
import soundfile as sf
from kokoro_onnx import Kokoro

LINES = [
    "Good morning. GRACI is online and ready.",
    "I found the failure. The test is expecting a different routing decision than the current implementation provides.",
    "The 4090 is unavailable because ModOrganizer is running. I will continue using the 3090.",
    "All tests passed. The implementation is ready for review.",
    "I found two relevant memories from this project. Neither conflicts with the current task.",
    "I would not make that change yet. The evidence does not support it.",
]
VOICES = ("af_heart", "af_bella", "af_nicole")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--voices", required=True)
    args = parser.parse_args()
    process = psutil.Process(os.getpid())
    rss = process.memory_info().rss
    started = time.perf_counter()
    pipeline = Kokoro(args.model, args.voices)
    load_seconds = time.perf_counter() - started
    rows = []
    for voice in VOICES:
        for index, text in enumerate(LINES, 1):
            out = args.output / voice / f"line-{index:02d}.wav"
            out.parent.mkdir(parents=True, exist_ok=True)
            began = time.perf_counter()
            audio, sample_rate = pipeline.create(text, voice=voice, speed=1.0, lang="en-us")
            elapsed = time.perf_counter() - began
            sf.write(out, audio, sample_rate)
            rows.append({"voice": voice, "line": index, "text": text,
                         "file": out.as_posix(), "audio_seconds": round(len(audio) / sample_rate, 3),
                         "generation_seconds": round(elapsed, 3),
                         "real_time_factor": round(elapsed / (len(audio) / sample_rate), 3)})
    result = {"schema_version": 1, "engine": "Kokoro-82M ONNX", "package_version": "kokoro-onnx 0.4.9",
              "mode": "cpu", "cold_pipeline_seconds": round(load_seconds, 3),
              "rss_delta_bytes_lower_bound": max(0, process.memory_info().rss - rss), "results": rows}
    (args.output.parent / "kokoro-generation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
