"""FPS-Bench: a benchmark for high-frame-rate video understanding.

This package contains the reusable library code behind the public release of
FPS-Bench. It is intentionally lightweight: the core import (``import fpsbench``)
pulls in only the Python standard library. Heavy/optional dependencies (pandas,
yt-dlp, ffmpeg, opencv, model backends) are declared as extras in
``pyproject.toml`` and imported lazily inside the modules and scripts that need
them.
"""

__version__ = "1.0.0"

# Canonical dataset version shipped with this release. This is distinct from the
# package ``__version__`` above, though they happen to match for v1.0.0.
DATASET_VERSION = "1.0.0"

# The nine task categories, normalized to lowercase snake_case. This is the
# single source of truth used by the schema, ingestion, and validation.
TASK_CATEGORIES = (
    "repetitive_motion",
    "speed_recognition",
    "fine_grained_motion",
    "action_order",
    "state_at_event",
    "blink_and_miss",
    "causality_detection",
    "synchronization_assessment",
    "instance_count",
)

# Valid multiple-choice answer letters.
ANSWER_CHOICES = ("A", "B", "C", "D", "E")
