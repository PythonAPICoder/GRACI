"""Run one bounded local Kokoro synthesis and record non-audio evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from graci.tts import (AuthoritativeFinalResponse, KokoroConfig,
                       KokoroSubprocessTTS, TTSRequest)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = ROOT / "phase6a" / ".venv312" / "Scripts" / "python.exe"
DEFAULT_MODEL = ROOT / "phase6a" / "cache" / "kokoro-onnx" / "kokoro-v1.0.int8.onnx"
DEFAULT_VOICES = ROOT / "phase6a" / "cache" / "kokoro-onnx" / "voices-v1.0.bin"
DEFAULT_EVIDENCE = ROOT / "phase6d" / "evidence" / "live-kokoro-synthesis.json"
FIXTURE = "GRACI is ready. The 3090 remains authoritative."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--voices", type=Path, default=DEFAULT_VOICES)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    adapter = KokoroSubprocessTTS(KokoroConfig(
        args.python, ROOT / "phase6d" / "tts_worker.py", args.model, args.voices))
    result = adapter.synthesize(TTSRequest(AuthoritativeFinalResponse(FIXTURE)))
    payload = {
        "schema_version": 1,
        "phase": "6D",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if result.succeeded else "FAIL",
        "engine": result.engine,
        "voice": result.voice,
        "device": "cpu",
        "local_assets_only": True,
        "python_executable": str(args.python.relative_to(ROOT)),
        "authoritative_text": result.authoritative_text,
        "speech_presentation_text": result.presentation_text,
        "authoritative_text_mutated": result.authoritative_text != FIXTURE,
        "audio_retained": False,
        "physical_playback_performed": False,
        "error_code": result.error_code,
        "error_message": result.error_message,
    }
    if result.audio is not None:
        payload["audio"] = {
            "bytes": len(result.audio.wav_bytes),
            "seconds": round(result.audio.duration_seconds, 3),
            "sample_rate": result.audio.sample_rate,
            "channels": result.audio.channels,
            "sample_width": result.audio.sample_width,
            "sha256": hashlib.sha256(result.audio.wav_bytes).hexdigest(),
        }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if result.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
