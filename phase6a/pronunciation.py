"""Bounded deterministic speech-only pronunciation overrides for Phase 6."""
from __future__ import annotations

import re
from types import MappingProxyType

from graci.speech_normalization import normalize_spoken_text

MAX_TTS_TEXT_CHARS = 20_000
MAX_PRONUNCIATION_ENTRIES = 32

# Keys remain canonical written forms; values are presentation-only TTS spellings.
TECHNICAL_PRONUNCIATIONS = MappingProxyType({
    "GRACI": "GRAY-see",
    "3090": "thirty ninety",
    "4090": "forty ninety",
})


def speech_presentation_text(authoritative_text: str) -> str:
    """Return a speech-only rendering without mutating authoritative text."""
    if not isinstance(authoritative_text, str):
        raise TypeError("authoritative_text must be a string")
    if len(authoritative_text) > MAX_TTS_TEXT_CHARS:
        raise ValueError("authoritative_text exceeds the TTS presentation bound")
    if len(TECHNICAL_PRONUNCIATIONS) > MAX_PRONUNCIATION_ENTRIES:
        raise RuntimeError("technical pronunciation lexicon exceeds its bound")
    # Presentation syntax is removed first so the pronunciation lexicon always
    # operates on the final speech copy and can still pronounce GRACI in headings,
    # emphasis, link labels, and protected technical content.
    rendered = normalize_spoken_text(authoritative_text)
    for written, spoken in TECHNICAL_PRONUNCIATIONS.items():
        rendered = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(written)}(?![A-Za-z0-9_])",
                          spoken, rendered)
    return rendered
