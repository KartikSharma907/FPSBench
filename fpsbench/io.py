"""Reading and writing FPS-Bench artifacts (JSONL, CSV).

JSONL is the canonical format — one nested record per line. The CSV is a
flattened mirror generated from the same records (via ``flatten_record``), so it
can't drift out of sync.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List

__all__ = [
    "read_jsonl",
    "write_jsonl",
    "flatten_record",
    "flat_fieldnames",
    "write_csv",
]


def read_jsonl(path) -> List[Dict[str, Any]]:
    """Read a JSONL file into a list of dicts. Skips blank lines."""
    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{i}: invalid JSON: {e}") from e
    return records


def iter_jsonl(path) -> Iterator[Dict[str, Any]]:
    """Lazily iterate over a JSONL file."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path, records: Iterable[Dict[str, Any]]) -> int:
    """Write records to JSONL. Returns the number of records written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=False))
            f.write("\n")
            n += 1
    return n


# Stable, human-friendly column order for the flat (CSV/XLSX) mirrors.
_FLAT_FIELDS = [
    "id",
    "version",
    "split",
    "source_dataset",
    "source_platform",
    "source_video_id",
    "source_url",
    "video_available_at_release",
    "availability_checked_utc",
    "clip_start_sec",
    "clip_end_sec",
    "clip_duration_sec",
    "temporal_certificate_start_sec",
    "temporal_certificate_end_sec",
    "temporal_certificate_duration_sec",
    "raw_clip_range",
    "raw_temporal_certificate",
    "question_text",
    "question_type",
    "choice_a",
    "choice_b",
    "choice_c",
    "choice_d",
    "choice_e",
    "answer",
    "answer_text",
    "min_fps",
    "min_required_frames_for_certificate",
    "native_fps",
    "task_category",
    "visual_domain",
    "visual_domain_fine",
    "visual_subdomain",
    "source_video_category",
    "original_row_id",
]


def flat_fieldnames() -> List[str]:
    """The CSV column order, matching ``flatten_record``."""
    return list(_FLAT_FIELDS)


def flatten_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten a nested record into the single-level row used for the CSV."""
    src = rec["source"]
    t = rec["time"]
    q = rec["question"]
    ch = q["choices"]
    tr = rec["temporal_requirements"]
    cats = rec["categories"]
    meta = rec["metadata"]
    return {
        "id": rec["id"],
        "version": rec["version"],
        "split": rec["split"],
        "source_dataset": src["dataset"],
        "source_platform": src["platform"],
        "source_video_id": src["video_id"],
        "source_url": src["url"],
        "video_available_at_release": src.get("video_available_at_release"),
        "availability_checked_utc": src.get("availability_checked_utc"),
        "clip_start_sec": t["clip_start_sec"],
        "clip_end_sec": t["clip_end_sec"],
        "clip_duration_sec": t["clip_duration_sec"],
        "temporal_certificate_start_sec": t["temporal_certificate_start_sec"],
        "temporal_certificate_end_sec": t["temporal_certificate_end_sec"],
        "temporal_certificate_duration_sec": t["temporal_certificate_duration_sec"],
        "raw_clip_range": t["raw_clip_range"],
        "raw_temporal_certificate": t["raw_temporal_certificate"],
        "question_text": q["text"],
        "question_type": q["type"],
        "choice_a": ch.get("A"),
        "choice_b": ch.get("B"),
        "choice_c": ch.get("C"),
        "choice_d": ch.get("D"),
        "choice_e": ch.get("E"),
        "answer": q.get("answer"),
        "answer_text": q.get("answer_text"),
        "min_fps": tr["min_fps"],
        "min_required_frames_for_certificate": tr["min_required_frames_for_certificate"],
        "native_fps": tr.get("native_fps"),
        "task_category": cats["task_category"],
        "visual_domain": cats["visual_domain"],
        "visual_domain_fine": cats["visual_domain_fine"],
        "visual_subdomain": cats["visual_subdomain"],
        "source_video_category": cats.get("source_video_category"),
        "original_row_id": meta["original_row_id"],
    }


def write_csv(path, records: Iterable[Dict[str, Any]]) -> int:
    """Write flattened records to CSV. Returns the number of rows written."""
    import csv

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FLAT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow(flatten_record(rec))
            n += 1
    return n
