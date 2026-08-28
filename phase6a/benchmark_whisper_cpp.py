from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

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
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = {r["line"]: r for r in json.loads(args.manifest.read_text(encoding="utf-8"))["results"] if r["kind"] == "corpus"}
    rows = []
    for path in sorted(args.corpus.glob("*.wav")):
        number = int(path.stem.split("-")[-1])
        started = time.perf_counter()
        run = subprocess.run([str(args.binary), "-m", str(args.model), "-f", str(path),
                              "-l", "en", "-nt", "-np"], capture_output=True, text=True, check=False)
        elapsed = time.perf_counter() - started
        transcript = run.stdout.strip()
        reference = expected[number]["text"]
        audio = expected[number]["seconds"]
        rows.append({"line": number, "reference": reference, "transcript": transcript,
                     "audio_seconds": audio, "transcription_seconds": round(elapsed, 3),
                     "real_time_factor": round(elapsed / audio, 3), "exit_code": run.returncode,
                     "word_errors": distance(norm(reference), norm(transcript)),
                     "reference_words": len(norm(reference)), "stderr_tail": run.stderr[-300:]})
    total_audio = sum(r["audio_seconds"] for r in rows)
    total_elapsed = sum(r["transcription_seconds"] for r in rows)
    result = {"schema_version": 1, "engine": "whisper.cpp", "version": "b4938",
              "model": args.model.name, "device": "cpu", "model_bytes": args.model.stat().st_size,
              "total_audio_seconds": round(total_audio, 3), "total_transcription_seconds": round(total_elapsed, 3),
              "aggregate_rtf_including_process_start": round(total_elapsed / total_audio, 3),
              "wer": round(sum(r["word_errors"] for r in rows) / sum(r["reference_words"] for r in rows), 4),
              "results": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
