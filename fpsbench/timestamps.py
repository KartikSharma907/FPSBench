"""Robust timestamp parsing for FPS-Bench annotations.

The raw spreadsheet stores time intervals as human-typed strings such as
``"1:40 - 1:46"`` or ``"0:08-0:12"``. This module turns those into floating
point seconds while being strict enough to *flag* (never silently drop)
malformed values.

Design goals:

* Accept ``M:SS``, ``MM:SS`` and ``H:MM:SS`` single timestamps.
* Accept ranges joined by ``-`` or `` - `` (and a few unicode dash variants).
* Return seconds as floats and always preserve the raw input string.
* Repair a small, well understood set of known typos *deterministically* and
  record that a repair happened, rather than guessing.
* Raise :class:`TimestampError` for anything ambiguous so callers can flag the
  row for review (or exclude it).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

__all__ = [
    "TimestampError",
    "ParsedInterval",
    "parse_timestamp",
    "parse_interval",
]

# Dash characters we treat as range separators (ascii hyphen, en dash, em dash,
# minus sign). Normalized to a plain hyphen before parsing.
_DASHES = "-‐‑‒–—−"
_DASH_RE = re.compile(f"[{_DASHES}]")

# A single timestamp: 1-2 optional hour digits, then minutes and seconds.
_SINGLE_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2})$")


class TimestampError(ValueError):
    """Raised when a timestamp / interval string cannot be safely parsed."""


@dataclass
class ParsedInterval:
    """Result of parsing a time-range string.

    Attributes:
        start_sec: interval start in seconds.
        end_sec: interval end in seconds.
        raw: the original, unmodified input string.
        repaired: ``True`` if a deterministic typo repair was applied.
        notes: human-readable notes describing any repairs (for the issue log).
    """

    start_sec: float
    end_sec: float
    raw: str
    repaired: bool = False
    notes: List[str] = field(default_factory=list)

    @property
    def duration_sec(self) -> float:
        return round(self.end_sec - self.start_sec, 6)


def parse_timestamp(value: str) -> float:
    """Parse a single ``M:SS`` / ``MM:SS`` / ``H:MM:SS`` timestamp to seconds.

    Raises:
        TimestampError: if the value is blank or not a recognizable timestamp.
    """
    if value is None:
        raise TimestampError("timestamp is None")
    text = str(value).strip()
    if not text:
        raise TimestampError("timestamp is empty")

    m = _SINGLE_RE.match(text)
    if not m:
        raise TimestampError(f"unrecognized timestamp: {value!r}")

    hours = int(m.group(1)) if m.group(1) is not None else 0
    minutes = int(m.group(2))
    seconds = int(m.group(3))
    if seconds >= 60 or minutes >= 60:
        raise TimestampError(f"minutes/seconds out of range in {value!r}")
    return float(hours * 3600 + minutes * 60 + seconds)


def _attempt_known_repairs(text: str) -> tuple[str, Optional[str]]:
    """Deterministically repair a small set of known spreadsheet typos.

    Returns the (possibly repaired) string and a note describing the repair, or
    ``(text, None)`` if no repair applied. Only repairs that are unambiguous are
    performed; anything else is left for :func:`parse_interval` to reject.
    """
    note = None

    # Known issue 1: "0:49-0.53" -> the second separator uses '.' where ':' was
    # clearly intended (the surrounding pattern is M:SS-M.SS). Repair only when
    # the shape is exactly digit(s).digit{2} on one side of the dash.
    m = re.match(r"^(\d{1,2}:\d{2})\s*-\s*(\d{1,2})\.(\d{2})$", text)
    if m:
        repaired = f"{m.group(1)}-{m.group(2)}:{m.group(3)}"
        return repaired, f"repaired '.' to ':' in end timestamp ({text!r} -> {repaired!r})"

    # Known issue 2: "0:19:0:21" -> a range written with ':' instead of '-'
    # between the two M:SS timestamps. Repair only the very specific shape
    # M:SS:M:SS (four colon-separated 1-2 digit groups).
    m = re.match(r"^(\d{1,2}):(\d{2}):(\d{1,2}):(\d{2})$", text)
    if m:
        repaired = f"{m.group(1)}:{m.group(2)}-{m.group(3)}:{m.group(4)}"
        return repaired, f"repaired ':' to '-' as range separator ({text!r} -> {repaired!r})"

    return text, note


def parse_interval(value: str) -> ParsedInterval:
    """Parse a time *range* string into a :class:`ParsedInterval`.

    Accepts a single timestamp (start only) by treating start == end, but the
    benchmark always expects a real range, so callers should additionally
    enforce ``start < end`` via validation.

    Raises:
        TimestampError: if the value cannot be safely parsed (after attempting
            the known deterministic repairs).
    """
    if value is None:
        raise TimestampError("interval is None")
    raw = str(value).strip()
    if not raw:
        raise TimestampError("interval is empty")

    text, note = _attempt_known_repairs(raw)
    repaired = note is not None
    notes = [note] if note else []

    normalized = _DASH_RE.sub("-", text)
    parts = [p.strip() for p in normalized.split("-") if p.strip() != ""]

    if len(parts) == 1:
        # Single timestamp; treat as a zero-length interval. Validation will
        # reject this for required clip/certificate fields.
        sec = parse_timestamp(parts[0])
        return ParsedInterval(sec, sec, raw, repaired, notes)
    if len(parts) != 2:
        raise TimestampError(f"expected a single range 'A-B', got {value!r}")

    start = parse_timestamp(parts[0])
    end = parse_timestamp(parts[1])
    return ParsedInterval(start, end, raw, repaired, notes)
