"""Deterministic presentation-only normalization for spoken responses."""

from __future__ import annotations

import re


_PROTECTED = re.compile(
    r"```(?:[^`]|`(?!``))*```|`([^`\n]+)`|\$\$.*?\$\$|(?<!\$)\$[^\n$]+\$",
    re.DOTALL,
)
_LINK = re.compile(r"!?\[([^\]\n]+)\]\((?:[^()\s]+|\([^()]*\))+\)")
_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", re.DOTALL)
_ITALIC = re.compile(r"(?<![\w*])([*_])(?=\S)([^\n]*?\S)\1(?![\w*])")
_STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.DOTALL)
_HEADING = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+")
_BULLET = re.compile(r"(?m)^[ \t]{0,3}(?:[-+*]|\d{1,3}[.)])[ \t]+")
_DECORATIVE_LINE = re.compile(r"(?m)^[ \t]*([*#_=~\-])(?:[ \t]*\1){2,}[ \t]*$")
_DECORATIVE_RUN = re.compile(r"(?<!\w)([*#_=~])\1{2,}(?!\w)")


def normalize_spoken_text(text: str) -> str:
    """Remove presentation syntax while retaining protected literal/code/math content.

    This function operates only on an independently derived TTS copy. Inline and
    fenced code plus dollar-delimited mathematics retain their meaningful symbols;
    Markdown backticks themselves are presentation delimiters and are removed.
    """
    if not isinstance(text, str):
        raise TypeError("spoken text must be a string")

    protected: list[str] = []

    def protect(match: re.Match[str]) -> str:
        value = match.group(0)
        if value.startswith("```"):
            first_newline = value.find("\n")
            value = (value[first_newline + 1:-3] if first_newline >= 0 else value[3:-3])
        elif value.startswith("`"):
            value = match.group(1) or ""
        protected.append(value)
        return f"\ue000{len(protected) - 1}\ue001"

    rendered = _PROTECTED.sub(protect, text)
    rendered = _LINK.sub(lambda match: match.group(1), rendered)
    rendered = _HEADING.sub("", rendered)
    rendered = _BULLET.sub("", rendered)
    rendered = _DECORATIVE_LINE.sub("", rendered)
    rendered = _DECORATIVE_RUN.sub("", rendered)
    rendered = _BOLD.sub(lambda match: match.group(2), rendered)
    rendered = _ITALIC.sub(lambda match: match.group(2), rendered)
    rendered = _STRIKE.sub(lambda match: match.group(1), rendered)

    for index, value in enumerate(protected):
        rendered = rendered.replace(f"\ue000{index}\ue001", value)
    return rendered
