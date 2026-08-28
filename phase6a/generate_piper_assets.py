from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

CORPUS = [
    "GRACI, inspect the repository and tell me what failed.",
    "Run the tests and explain the result.",
    "Use the 3090 unless optional capacity is available.",
    "Do not use the 4090 while ModOrganizer is running.",
    "What do you remember about this project?",
    "Review the latest implementation.", "Qwen", "GLM", "llama.cpp", "GitHub",
    "PowerShell", "Phase six", "visualizer", "adjudication",
]
AUDITION = [
    "Good morning. GRACI is online and ready.",
    "I found the failure. The test is expecting a different routing decision than the current implementation provides.",
    "The 4090 is unavailable because ModOrganizer is running. I will continue using the 3090.",
    "All tests passed. The implementation is ready for review.",
    "I found two relevant memories from this project. Neither conflicts with the current task.",
    "I would not make that change yet. The evidence does not support it.",
]

def duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()

def synth(python: Path, model: Path, text: str, output: Path) -> float:
    output.parent.mkdir(parents=True, exist_ok=True)
    source = output.with_suffix(".txt")
    source.write_text(text + "\n", encoding="utf-8")
    started = time.perf_counter()
    subprocess.run([str(python), "-m", "piper", "-m", str(model), "-i", str(source),
                    "-f", str(output)], check=True, capture_output=True, text=True)
    source.unlink()
    return time.perf_counter() - started

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voices", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    python = Path(sys.executable)
    voices = sorted(args.voices.glob("*.onnx"))
    rows = []
    corpus_voice = next(v for v in voices if "lessac" in v.name)
    for index, text in enumerate(CORPUS, 1):
        out = args.output / "corpus" / f"phrase-{index:02d}.wav"
        elapsed = synth(python, corpus_voice, text, out)
        rows.append({"kind": "corpus", "voice": corpus_voice.stem, "line": index,
                     "text": text, "file": out.as_posix(), "seconds": round(duration(out), 3),
                     "generation_seconds": round(elapsed, 3)})
    for voice in voices:
        for index, text in enumerate(AUDITION, 1):
            out = args.output / "audition" / voice.stem / f"line-{index:02d}.wav"
            elapsed = synth(python, voice, text, out)
            rows.append({"kind": "audition", "voice": voice.stem, "line": index,
                         "text": text, "file": out.as_posix(), "seconds": round(duration(out), 3),
                         "generation_seconds": round(elapsed, 3)})
    (args.output / "piper-generation.json").write_text(
        json.dumps({"schema_version": 1, "synthetic_non_private": True, "results": rows}, indent=2) + "\n",
        encoding="utf-8")

if __name__ == "__main__":
    main()
