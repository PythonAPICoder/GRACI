from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import time
from pathlib import Path

import psutil
from faster_whisper import WhisperModel

def norm(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())

def distance(a: list[str], b: list[str]) -> int:
    prior = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        row = [i]
        for j, right in enumerate(b, 1):
            row.append(min(row[-1] + 1, prior[j] + 1, prior[j - 1] + (left != right)))
        prior = row
    return prior[-1]

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), required=True)
    parser.add_argument("--compute-type", required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = {r["line"]: r for r in json.loads(args.manifest.read_text(encoding="utf-8"))["results"] if r["kind"] == "corpus"}
    process = psutil.Process(os.getpid())
    cpu_before = process.cpu_times()
    rss_before = process.memory_info().rss
    load_start = time.perf_counter()
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type,
                         download_root=str(args.cache), local_files_only=False)
    load_seconds = time.perf_counter() - load_start
    rows = []
    for path in sorted(args.corpus.glob("*.wav")):
        number = int(path.stem.split("-")[-1])
        started = time.perf_counter()
        segments, info = model.transcribe(str(path), language="en", beam_size=5,
                                          vad_filter=False, condition_on_previous_text=False)
        transcript = " ".join(segment.text.strip() for segment in segments).strip()
        elapsed = time.perf_counter() - started
        audio_seconds = expected[number]["seconds"]
        reference = expected[number]["text"]
        ref_words, got_words = norm(reference), norm(transcript)
        rows.append({"line": number, "reference": reference, "transcript": transcript,
                     "audio_seconds": audio_seconds, "transcription_seconds": round(elapsed, 3),
                     "real_time_factor": round(elapsed / audio_seconds, 3),
                     "word_errors": distance(ref_words, got_words), "reference_words": len(ref_words),
                     "language_probability": round(info.language_probability, 4)})
    cpu_after = process.cpu_times()
    total_audio = sum(r["audio_seconds"] for r in rows)
    total_elapsed = sum(r["transcription_seconds"] for r in rows)
    result = {"schema_version": 1, "engine": "faster-whisper", "engine_version": "1.2.1",
              "model": args.model, "device": args.device, "compute_type": args.compute_type,
              "platform": platform.platform(), "cold_model_load_seconds": round(load_seconds, 3),
              "total_audio_seconds": round(total_audio, 3), "total_transcription_seconds": round(total_elapsed, 3),
              "aggregate_rtf": round(total_elapsed / total_audio, 3),
              "median_rtf": round(statistics.median(r["real_time_factor"] for r in rows), 3),
              "wer": round(sum(r["word_errors"] for r in rows) / sum(r["reference_words"] for r in rows), 4),
              "process_cpu_seconds": round((cpu_after.user + cpu_after.system) - (cpu_before.user + cpu_before.system), 3),
              "peak_rss_delta_bytes_lower_bound": max(0, process.memory_info().rss - rss_before),
              "results": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
