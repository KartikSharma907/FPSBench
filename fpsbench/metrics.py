"""Scoring and metrics for FPS-Bench predictions."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Dict, List, Optional, Sequence

__all__ = ["min_fps_bucket", "duration_bucket", "compute_metrics", "RANDOM_BASELINE_5WAY"]

# Expected accuracy of uniform random guessing over 5 options.
RANDOM_BASELINE_5WAY = 0.2


def min_fps_bucket(min_fps: Optional[float]) -> str:
    """Bucket a minFPS value into the reporting bins used in the paper/README."""
    if min_fps is None:
        return "unknown"
    v = float(min_fps)
    if v <= 4:
        return "4"
    if v == 5:
        return "5"
    if v == 6:
        return "6"
    if v == 7:
        return "7"
    if 8 <= v <= 10:
        return "8-10"
    return "10+"


def duration_bucket(duration_sec: Optional[float]) -> str:
    """Bucket a clip duration (seconds) into coarse bins."""
    if duration_sec is None:
        return "unknown"
    v = float(duration_sec)
    if v <= 2:
        return "0-2"
    if v <= 5:
        return "2-5"
    if v <= 10:
        return "5-10"
    if v <= 20:
        return "10-20"
    return "20+"


def _accuracy(correct: int, total: int) -> float:
    return (correct / total) if total else 0.0


def _grouped_accuracy(rows: Sequence[Dict], key: str) -> Dict[str, Dict[str, float]]:
    groups: Dict[str, List[int]] = defaultdict(list)
    for r in rows:
        if r.get("correct") is None:
            continue
        groups[str(r.get(key))].append(1 if r["correct"] else 0)
    out = {}
    for k, vals in sorted(groups.items()):
        out[k] = {
            "count": len(vals),
            "correct": sum(vals),
            "accuracy": _accuracy(sum(vals), len(vals)),
        }
    return out


def _bootstrap_ci(
    rows: Sequence[Dict], *, iterations: int = 1000, seed: int = 0
) -> Optional[List[float]]:
    """95% bootstrap CI for overall accuracy. Returns ``[lo, hi]`` or None."""
    scored = [1 if r["correct"] else 0 for r in rows if r.get("correct") is not None]
    if len(scored) < 2:
        return None
    rng = random.Random(seed)
    n = len(scored)
    means = []
    for _ in range(iterations):
        sample = [scored[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * iterations)]
    hi = means[min(int(0.975 * iterations), iterations - 1)]
    return [round(lo, 4), round(hi, 4)]


def compute_metrics(rows: Sequence[Dict], *, bootstrap: bool = True) -> Dict:
    """Compute the full metrics report from a list of scored result rows.

    Each row is expected to carry at least ``correct`` (bool or None for
    no-answer), plus optional grouping keys (``task_category``,
    ``visual_domain``, ``visual_subdomain``, ``min_fps``, ``clip_duration_sec``).
    """
    total = len(rows)
    scored = [r for r in rows if r.get("correct") is not None]
    correct = sum(1 for r in scored if r["correct"])
    invalid = sum(1 for r in rows if r.get("prediction") in (None, "", "UNKNOWN"))

    # Bucket helpers add derived keys on the fly without mutating inputs.
    fps_rows = [dict(r, _fps_bucket=min_fps_bucket(r.get("min_fps"))) for r in rows]
    dur_rows = [
        dict(r, _dur_bucket=duration_bucket(r.get("clip_duration_sec"))) for r in rows
    ]

    report = {
        "num_results": total,
        "num_scored": len(scored),
        "overall_accuracy": _accuracy(correct, len(scored)),
        "random_baseline": RANDOM_BASELINE_5WAY,
        "no_answer_rate": _accuracy(invalid, total),
        "num_invalid_or_no_answer": invalid,
        "accuracy_by_task_category": _grouped_accuracy(rows, "task_category"),
        "accuracy_by_visual_domain": _grouped_accuracy(rows, "visual_domain"),
        "accuracy_by_visual_subdomain": _grouped_accuracy(rows, "visual_subdomain"),
        "accuracy_by_min_fps_bucket": _grouped_accuracy(fps_rows, "_fps_bucket"),
        "accuracy_by_clip_duration_bucket": _grouped_accuracy(dur_rows, "_dur_bucket"),
    }
    if bootstrap:
        ci = _bootstrap_ci(scored)
        if ci is not None:
            report["overall_accuracy_95ci"] = ci
    return report
