"""FPS-Bench: a benchmark for high-frame-rate video understanding.

The library code behind the public release. ``import fpsbench`` needs only the
standard library; the heavier optional dependencies (pandas, yt-dlp, ffmpeg,
opencv, model backends) are declared as extras in ``pyproject.toml`` and imported
lazily where they're actually used.
"""

__version__ = "1.0.0"

# Version of the dataset itself, separate from the package version above (they
# happen to match at 1.0.0).
DATASET_VERSION = "1.0.0"

# The nine task categories in lowercase snake_case. The schema, ingestion, and
# validation all read them from here.
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
