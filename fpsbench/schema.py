"""The FPS-Bench annotation schema and record validation.

This module defines the shape of one JSONL record. It provides:

* :func:`build_json_schema` -- a JSON Schema (draft 2020-12) document, written to
  ``annotations/fpsbench_v1.schema.json`` so you can validate your copy with any
  standard validator.
* :func:`validate_record` -- a dependency-free validator that returns a list of
  error strings (empty means valid). The ingestion and validation scripts use it.
  It mirrors the JSON Schema but adds the cross-field checks (e.g. the clip
  contains the certificate) that plain JSON Schema can't express.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import ANSWER_CHOICES, DATASET_VERSION, TASK_CATEGORIES

__all__ = ["build_json_schema", "validate_record", "MIN_FPS_FLOOR"]

# Minimum allowed minFPS per the paper's curation threshold.
MIN_FPS_FLOOR = 4

# Required A-D choices (E is optional but expected to be "None of the above").
_REQUIRED_CHOICES = ("A", "B", "C", "D")
_NONE_OF_ABOVE = "None of the above"


def build_json_schema() -> Dict[str, Any]:
    """Return the JSON Schema (draft 2020-12) for one FPS-Bench record."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/fps-bench/fpsbench/annotations/fpsbench_v1.schema.json",
        "title": "FPS-Bench annotation record",
        "description": "One video-question-answer example in FPS-Bench v1.",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "version",
            "split",
            "source",
            "time",
            "question",
            "temporal_requirements",
            "categories",
            "metadata",
        ],
        "properties": {
            "id": {"type": "string", "pattern": r"^fpsbench_\d{6}$"},
            "version": {"type": "string"},
            "split": {"type": "string", "enum": ["test"]},
            "source": {
                "type": "object",
                "additionalProperties": False,
                "required": ["dataset", "platform", "video_id", "url"],
                "properties": {
                    "dataset": {"type": "string"},
                    "platform": {"type": "string"},
                    "video_id": {"type": "string", "pattern": r"^[A-Za-z0-9_-]{11}$"},
                    "url": {"type": "string"},
                    "video_available_at_release": {"type": ["boolean", "null"]},
                    "availability_checked_utc": {"type": ["string", "null"]},
                },
            },
            "time": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "clip_start_sec",
                    "clip_end_sec",
                    "clip_duration_sec",
                    "temporal_certificate_start_sec",
                    "temporal_certificate_end_sec",
                    "temporal_certificate_duration_sec",
                    "raw_clip_range",
                    "raw_temporal_certificate",
                ],
                "properties": {
                    "clip_start_sec": {"type": "number", "minimum": 0},
                    "clip_end_sec": {"type": "number", "minimum": 0},
                    "clip_duration_sec": {"type": "number", "exclusiveMinimum": 0},
                    "temporal_certificate_start_sec": {"type": "number", "minimum": 0},
                    "temporal_certificate_end_sec": {"type": "number", "minimum": 0},
                    "temporal_certificate_duration_sec": {"type": "number", "exclusiveMinimum": 0},
                    "raw_clip_range": {"type": "string"},
                    "raw_temporal_certificate": {"type": "string"},
                },
            },
            "question": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "type", "choices", "answer", "answer_text"],
                "properties": {
                    "text": {"type": "string", "minLength": 1},
                    "type": {"type": "string", "enum": list(TASK_CATEGORIES)},
                    "choices": {
                        "type": "object",
                        "minProperties": 4,
                        "propertyNames": {"enum": list(ANSWER_CHOICES)},
                        "additionalProperties": {"type": "string"},
                    },
                    "answer": {"type": "string", "enum": list(ANSWER_CHOICES)},
                    "answer_text": {"type": "string", "minLength": 1},
                },
            },
            "temporal_requirements": {
                "type": "object",
                "additionalProperties": False,
                "required": ["min_fps", "min_required_frames_for_certificate", "native_fps"],
                "properties": {
                    "min_fps": {"type": "number", "minimum": MIN_FPS_FLOOR},
                    "min_required_frames_for_certificate": {"type": ["integer", "null"], "minimum": 0},
                    "native_fps": {"type": ["number", "null"]},
                },
            },
            "categories": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "task_category",
                    "visual_domain",
                    "visual_domain_fine",
                    "visual_subdomain",
                    "source_video_category",
                ],
                "properties": {
                    "task_category": {"type": "string", "enum": list(TASK_CATEGORIES)},
                    "visual_domain": {"type": "string"},
                    "visual_domain_fine": {"type": "string"},
                    "visual_subdomain": {"type": "string"},
                    "source_video_category": {"type": ["string", "null"]},
                },
            },
            "metadata": {
                "type": "object",
                "additionalProperties": False,
                "required": ["original_row_id", "source_dataset"],
                "properties": {
                    "original_row_id": {"type": "integer", "minimum": 0},
                    "source_dataset": {"type": "string"},
                },
            },
        },
    }


def validate_record(record: Dict[str, Any], *, include_warnings: bool = False) -> List[str]:
    """Validate one record. Returns a list of error strings (empty == valid).

    We don't lean on a JSON Schema library here: this also runs the cross-field
    checks plain JSON Schema can't express (durations are consistent, the answer
    dereferences a real choice, no private fields leak).

    The "certificate contained within the clip" check is a warning, not a
    critical error. A handful of rows have the certificate slightly outside the
    clip; they're kept and documented under the README's "Data quality" section
    rather than excluded. Pass ``include_warnings=True`` to append those
    (prefixed with ``"WARNING: "``).
    """
    errors: List[str] = []
    warnings: List[str] = []

    def req(obj, key, kind=None):
        if key not in obj or obj[key] is None:
            errors.append(f"missing required field: {key}")
            return None
        if kind is not None and not isinstance(obj[key], kind):
            errors.append(f"field {key} has wrong type: {type(obj[key]).__name__}")
        return obj[key]

    # Top level
    rid = req(record, "id", str)
    if isinstance(rid, str) and not _matches_id(rid):
        errors.append(f"id does not match fpsbench_NNNNNN: {rid!r}")
    req(record, "version", str)
    split = req(record, "split", str)
    if split is not None and split != "test":
        errors.append(f"split must be 'test', got {split!r}")

    source = req(record, "source", dict) or {}
    vid = source.get("video_id")
    if not vid or not _is_video_id(vid):
        errors.append(f"source.video_id invalid: {vid!r}")
    if not source.get("url"):
        errors.append("source.url is empty")

    time_obj = req(record, "time", dict) or {}
    _validate_time(time_obj, errors, warnings)

    q = req(record, "question", dict) or {}
    _validate_question(q, errors)

    tr = req(record, "temporal_requirements", dict) or {}
    min_fps = tr.get("min_fps")
    if not isinstance(min_fps, (int, float)):
        errors.append("temporal_requirements.min_fps must be numeric")
    elif min_fps < MIN_FPS_FLOOR:
        errors.append(f"min_fps {min_fps} is below floor {MIN_FPS_FLOOR}")

    cats = req(record, "categories", dict) or {}
    tc = cats.get("task_category")
    if tc not in TASK_CATEGORIES:
        errors.append(f"categories.task_category invalid: {tc!r}")
    for key in ("visual_domain", "visual_domain_fine", "visual_subdomain"):
        if not cats.get(key):
            errors.append(f"categories.{key} is empty")

    meta = req(record, "metadata", dict) or {}
    if not isinstance(meta.get("original_row_id"), int):
        errors.append("metadata.original_row_id must be an integer")

    # No internal/private fields may leak.
    for banned in ("annotator", "FPS Annotator 1", "media_S3_link"):
        if banned in record or banned in meta or banned in source:
            errors.append(f"banned internal field present: {banned}")

    if include_warnings:
        errors.extend(f"WARNING: {w}" for w in warnings)
    return errors


def _validate_time(time_obj: Dict[str, Any], errors: List[str], warnings: List[str]) -> None:
    keys = (
        "clip_start_sec",
        "clip_end_sec",
        "temporal_certificate_start_sec",
        "temporal_certificate_end_sec",
    )
    vals = {}
    for k in keys:
        v = time_obj.get(k)
        if not isinstance(v, (int, float)):
            errors.append(f"time.{k} must be numeric")
            return
        vals[k] = float(v)

    if not vals["clip_start_sec"] < vals["clip_end_sec"]:
        errors.append("clip_start_sec must be < clip_end_sec")
    if not vals["temporal_certificate_start_sec"] < vals["temporal_certificate_end_sec"]:
        errors.append("temporal_certificate_start_sec must be < temporal_certificate_end_sec")
    # Certificate must lie within the clip (inclusive).
    inside = (
        vals["clip_start_sec"] <= vals["temporal_certificate_start_sec"]
        and vals["temporal_certificate_end_sec"] <= vals["clip_end_sec"]
    )
    if not inside:
        warnings.append("temporal certificate interval is not contained within the clip interval")


def _validate_question(q: Dict[str, Any], errors: List[str]) -> None:
    if not q.get("text"):
        errors.append("question.text is empty")
    if q.get("type") not in TASK_CATEGORIES:
        errors.append(f"question.type invalid: {q.get('type')!r}")

    choices = q.get("choices")
    if not isinstance(choices, dict):
        errors.append("question.choices must be an object")
        return
    for letter in _REQUIRED_CHOICES:
        val = choices.get(letter)
        if val is None or str(val).strip() == "":
            errors.append(f"question.choices.{letter} is missing or empty")
        elif not isinstance(val, str):
            errors.append(f"question.choices.{letter} must be a string")
    if "E" in choices and choices["E"] != _NONE_OF_ABOVE:
        # E is expected to be the none-of-the-above sentinel.
        errors.append(f"question.choices.E should be {_NONE_OF_ABOVE!r}, got {choices['E']!r}")

    answer = q.get("answer")
    if answer not in ANSWER_CHOICES:
        errors.append(f"question.answer invalid: {answer!r}")
    elif answer not in choices:
        errors.append(f"question.answer {answer!r} does not reference an existing choice")

    if not q.get("answer_text"):
        errors.append("question.answer_text is empty")
    elif answer in choices and q.get("answer_text") != choices.get(answer):
        errors.append("question.answer_text does not match the referenced choice text")


def _matches_id(rid: str) -> bool:
    import re

    return bool(re.match(r"^fpsbench_\d{6}$", rid))


def _is_video_id(vid: str) -> bool:
    import re

    return bool(re.match(r"^[A-Za-z0-9_-]{11}$", str(vid)))
