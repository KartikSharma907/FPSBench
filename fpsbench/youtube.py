"""YouTube URL / video-ID helpers.

Small, tested, and dependency-free so it can be imported anywhere.
"""

from __future__ import annotations

import re
from typing import Optional

__all__ = ["extract_video_id", "is_valid_video_id", "canonical_watch_url"]

# YouTube IDs are 11 characters from the URL-safe base64 alphabet.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Ordered patterns covering watch, short (youtu.be), embed, shorts and the
# generic ``?v=`` query form. The first capturing group is the video id.
_URL_PATTERNS = (
    re.compile(r"(?:youtube\.com/watch\?(?:[^#]*&)?v=)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtu\.be/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/v/)([A-Za-z0-9_-]{11})"),
)


def extract_video_id(url: str) -> Optional[str]:
    """Return the 11-character YouTube video ID, or ``None`` if not found.

    Handles standard watch URLs, ``youtu.be`` short links, ``/embed/``,
    ``/shorts/`` and ``/v/`` forms, with or without extra query parameters.
    """
    if not url:
        return None
    text = str(url).strip()
    for pattern in _URL_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1)
    # Bare 11-char id passed directly.
    if _VIDEO_ID_RE.match(text):
        return text
    return None


def is_valid_video_id(video_id: Optional[str]) -> bool:
    """True if ``video_id`` looks like a syntactically valid YouTube ID."""
    return bool(video_id) and bool(_VIDEO_ID_RE.match(video_id))


def canonical_watch_url(video_id: str) -> str:
    """Build a canonical ``watch?v=`` URL from a video ID."""
    return f"https://www.youtube.com/watch?v={video_id}"
