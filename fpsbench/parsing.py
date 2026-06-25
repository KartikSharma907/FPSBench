"""Parsing a free-text model response into an A/B/C/D/E option letter."""

from __future__ import annotations

import re
from typing import Optional, Sequence

from . import ANSWER_CHOICES

__all__ = ["parse_answer", "PARSERS"]

# Phrases like "the answer is B" / "I would choose (C)" / "Option D".
_PHRASE_RE = re.compile(
    r"\b(?:answer|option|choice|select|choose|pick)\b[^A-Za-z0-9]{0,12}\(?([A-Ea-e])\b",
)
# A leading letter possibly wrapped/followed by punctuation: "A", "A.", "(B)", "C:".
_LEADING_RE = re.compile(r"^\s*\(?\*{0,2}([A-Ea-e])\b")


def _allowed(letters: Optional[Sequence[str]]) -> set:
    if letters:
        return {l.upper() for l in letters}
    return set(ANSWER_CHOICES)


def parse_answer(
    response: str,
    allowed_letters: Optional[Sequence[str]] = None,
    *,
    mode: str = "first_letter",
) -> Optional[str]:
    """Parse a model response into one of A/B/C/D/E (or ``None`` if not found).

    Args:
        response: the raw model text.
        allowed_letters: restrict to these letters (defaults to A-E).
        mode: one of ``"strict"`` (only a clean leading letter), ``"first_letter"``
            (leading letter, else an explicit "answer is X" phrase, else the first
            standalone option letter anywhere). ``"llm_judge"`` is intentionally
            not implemented here (disabled by default).
    """
    if response is None:
        return None
    text = str(response).strip()
    if not text:
        return None
    allowed = _allowed(allowed_letters)

    if mode == "llm_judge":
        raise NotImplementedError("llm_judge answer parsing is disabled by default")

    m = _LEADING_RE.match(text)
    if m and m.group(1).upper() in allowed:
        return m.group(1).upper()

    if mode == "strict":
        return None

    # first_letter (lenient) fallbacks:
    m = _PHRASE_RE.search(text)
    if m and m.group(1).upper() in allowed:
        return m.group(1).upper()

    # First standalone option letter anywhere (word-boundaried, uppercase only to
    # avoid matching the indefinite article "a" mid-sentence).
    for token in re.finditer(r"\b([A-E])\b", text):
        if token.group(1) in allowed:
            return token.group(1)
    return None


# Names exposed on the CLI.
PARSERS = ("strict", "first_letter", "llm_judge")
