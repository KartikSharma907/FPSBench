#!/usr/bin/env python3
"""Ingest the source spreadsheet into the canonical FPS-Bench release artifacts.

Reads the public-release Excel sheet, builds canonical JSONL records, and emits
the JSON Schema and a stats report. Rows with *critical* issues are excluded
from the released set (and reported); rows with *noncritical* issues are kept
and flagged (see the README "Data quality" section).

The leaderboard is held-out, so the *published* data file carries no answer key:

* Published (questions-only) -- ``fpsbench_v1.jsonl`` / ``.csv`` /
  ``.schema.json``. ``question.answer`` and ``answer_text`` are stripped. This is
  the canonical file users download and run inference against.
* Maintainer-only (never committed; ``.gitignore``'d) -- ``fpsbench_v1.full.jsonl``
  / ``.full.csv`` keep the answer key, and ``fpsbench_v1.answers.jsonl`` maps
  ``id -> answer``. These back the leaderboard's server-side scoring.

Usage:
    python scripts/ingest_release.py \
        --input-xlsx "FPS-Bench Public Release.xlsx" \
        --paper-pdf "CVPR2026_FPSBench.pdf" \
        --output-dir annotations \
        --version 1.0.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Make the package importable when run as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fpsbench import ANSWER_CHOICES, TASK_CATEGORIES  # noqa: E402
from fpsbench import categories as cat  # noqa: E402
from fpsbench import io as fio  # noqa: E402
from fpsbench import schema as fschema  # noqa: E402
from fpsbench.metrics import min_fps_bucket  # noqa: E402
from fpsbench.timestamps import ParsedInterval, TimestampError, parse_interval  # noqa: E402
from fpsbench.youtube import canonical_watch_url, extract_video_id, is_valid_video_id  # noqa: E402

# Paper claim used for the unique-video-count cross-check.
PAPER_UNIQUE_VIDEO_COUNT = 554
EXPECTED_INPUT_ROWS = 1000

# Internal/private columns that must never reach the release.
BANNED_COLUMNS = ("annotator", "fps_annotator_1", "media_s3_link")

REQUIRED_COLUMNS = (
    "video_category",
    "source_dataset",
    "source_link",
    "id",
    "category",
    "temporal_certificate",
    "duration_seconds",
    "mcq_q1_prompt",
    "q1_opt_a",
    "q1_opt_b",
    "q1_opt_c",
    "q1_opt_d",
    "q1_opt_e",
    "q1_correct_option",
    "min_fps",
)


def _norm_col(name: str) -> str:
    return "_".join(str(name).strip().lower().split())


def _clean(value) -> Optional[str]:
    """Return a stripped string, or None for blank/NaN."""
    import math

    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in ("nan", "none"):
        return None
    return text


class Issue:
    def __init__(self, row_id, severity, issue, detail="", value=""):
        self.row_id = row_id
        self.severity = severity  # "critical" | "noncritical"
        self.issue = issue
        self.detail = detail
        self.value = value

    def as_dict(self):
        return {
            "original_row_id": self.row_id,
            "severity": self.severity,
            "issue": self.issue,
            "detail": self.detail,
            "value": self.value,
        }


def load_rows(xlsx_path: str) -> List[Dict[str, Any]]:
    """Load the spreadsheet into a list of column-normalized dict rows.

    The master sheet uses a two-level header: row 1 is a column-group banner and
    row 2 holds the real field names, with data starting on row 3 (so
    ``header=1`` in zero-based pandas terms). Only rows that carry a source video
    link are real benchmark examples; trailing draft rows without a link are
    dropped here so they never reach the issue log.
    """
    import pandas as pd

    df = pd.read_excel(xlsx_path, sheet_name="Public Release Draft", header=1, engine="openpyxl")
    df.columns = [_norm_col(c) for c in df.columns]
    rows = df.to_dict(orient="records")
    return [r for r in rows if _clean(r.get("source_link"))]


def build_record(
    row: Dict[str, Any], version: str
) -> Tuple[Optional[Dict[str, Any]], List[Issue]]:
    """Build one canonical record from a normalized row.

    Returns ``(record_or_None, issues)``. If any critical issue is found the
    record is ``None`` (excluded from release) but issues are still returned.
    """
    issues: List[Issue] = []
    row_id = int(row["id"])

    # --- source / youtube id ---
    source_link = _clean(row.get("source_link"))
    video_id = extract_video_id(source_link) if source_link else None
    if not is_valid_video_id(video_id):
        issues.append(Issue(row_id, "critical", "url_cannot_parse_to_youtube_id",
                            "source_link did not yield a valid 11-char YouTube ID", str(source_link)))

    # --- timestamps ---
    clip: Optional[ParsedInterval] = None
    cert: Optional[ParsedInterval] = None
    raw_clip = _clean(row.get("duration_seconds")) or ""
    raw_cert = _clean(row.get("temporal_certificate")) or ""
    try:
        clip = parse_interval(raw_clip)
        if clip.repaired:
            issues.append(Issue(row_id, "noncritical", "timestamp_repaired", clip.notes[0] if clip.notes else "", raw_clip))
        if not clip.start_sec < clip.end_sec:
            issues.append(Issue(row_id, "critical", "malformed_timestamp", "clip_start_sec not < clip_end_sec", raw_clip))
    except TimestampError as e:
        issues.append(Issue(row_id, "critical", "malformed_timestamp", f"clip range: {e}", raw_clip))
    try:
        cert = parse_interval(raw_cert)
        if cert.repaired:
            issues.append(Issue(row_id, "noncritical", "timestamp_repaired", cert.notes[0] if cert.notes else "", raw_cert))
        if not cert.start_sec < cert.end_sec:
            issues.append(Issue(row_id, "critical", "malformed_timestamp", "certificate_start_sec not < certificate_end_sec", raw_cert))
    except TimestampError as e:
        issues.append(Issue(row_id, "critical", "malformed_timestamp", f"certificate range: {e}", raw_cert))

    if clip and cert and clip.start_sec < clip.end_sec and cert.start_sec < cert.end_sec:
        inside = clip.start_sec <= cert.start_sec and cert.end_sec <= clip.end_sec
        if not inside:
            issues.append(Issue(row_id, "noncritical", "certificate_outside_clip",
                                "temporal certificate not contained within clip", f"clip={raw_clip} cert={raw_cert}"))

    # --- question / choices ---
    question_text = _clean(row.get("mcq_q1_prompt"))
    if not question_text:
        issues.append(Issue(row_id, "critical", "missing_question", "mcq_q1_prompt empty", ""))

    choices: Dict[str, str] = {}
    for letter, col in zip(ANSWER_CHOICES, ("q1_opt_a", "q1_opt_b", "q1_opt_c", "q1_opt_d", "q1_opt_e")):
        val = _clean(row.get(col))
        if letter in ("A", "B", "C", "D") and val is None:
            issues.append(Issue(row_id, "critical", "missing_choice", f"choice {letter} ({col}) is empty", ""))
        if val is not None:
            choices[letter] = str(val)

    # --- answer ---
    raw_answer = _clean(row.get("q1_correct_option"))
    answer = raw_answer.upper() if raw_answer else None
    if answer not in ANSWER_CHOICES:
        issues.append(Issue(row_id, "critical", "invalid_answer_key", "correct option not in A-E", str(raw_answer)))
        answer_text = None
    elif answer not in choices:
        issues.append(Issue(row_id, "critical", "invalid_answer_key", f"answer {answer} has no matching choice", str(raw_answer)))
        answer_text = None
    else:
        answer_text = choices[answer]

    # --- task category ---
    task_category = cat.normalize_task_category(row.get("category"))
    if task_category not in TASK_CATEGORIES:
        issues.append(Issue(row_id, "critical", "invalid_task_category", "category not one of the nine", str(row.get("category"))))

    # --- min_fps ---
    min_fps = row.get("min_fps")
    import math
    if min_fps is None or (isinstance(min_fps, float) and math.isnan(min_fps)):
        issues.append(Issue(row_id, "critical", "missing_min_fps", "min_fps is empty", ""))
        min_fps_val = None
    else:
        # The master stores a fractional per-annotator minFPS; the release
        # reports the rounded integer minimum necessary frame rate.
        min_fps_val = int(round(float(min_fps)))
        if min_fps_val < fschema.MIN_FPS_FLOOR:
            issues.append(Issue(row_id, "critical", "min_fps_below_floor", f"min_fps {min_fps_val} < {fschema.MIN_FPS_FLOOR}", str(min_fps_val)))

    # --- visual taxonomy ---
    raw_video_cat = _clean(row.get("video_category"))
    domain_fine, subdomain, needs_review = cat.map_video_category(raw_video_cat)
    visual_domain = cat.to_paper_domain(domain_fine)
    if needs_review:
        if raw_video_cat is None:
            issues.append(Issue(row_id, "noncritical", "missing_video_category", "fell back to Other/Miscellaneous", ""))
        else:
            issues.append(Issue(row_id, "noncritical", "taxonomy_fallback", "raw category unmapped; fell back to Other/Miscellaneous", raw_video_cat))

    # If any critical issue, exclude the row.
    if any(i.severity == "critical" for i in issues):
        return None, issues

    # Build the canonical record (all critical fields are guaranteed present here).
    min_required_frames = int(round(min_fps_val * cert.duration_sec))
    record = {
        "id": f"fpsbench_{row_id:06d}",
        "version": version,
        "split": "test",
        "source": {
            "dataset": _clean(row.get("source_dataset")) or "youtube8m",
            "platform": "youtube",
            "video_id": video_id,
            "url": canonical_watch_url(video_id),
            "video_available_at_release": None,
            "availability_checked_utc": None,
        },
        "time": {
            "clip_start_sec": clip.start_sec,
            "clip_end_sec": clip.end_sec,
            "clip_duration_sec": clip.duration_sec,
            "temporal_certificate_start_sec": cert.start_sec,
            "temporal_certificate_end_sec": cert.end_sec,
            "temporal_certificate_duration_sec": cert.duration_sec,
            "raw_clip_range": raw_clip,
            "raw_temporal_certificate": raw_cert,
        },
        "question": {
            "text": question_text,
            "type": task_category,
            "choices": choices,
            "answer": answer,
            "answer_text": answer_text,
        },
        "temporal_requirements": {
            "min_fps": min_fps_val,
            "min_required_frames_for_certificate": min_required_frames,
            "native_fps": None,
        },
        "categories": {
            "task_category": task_category,
            "visual_domain": visual_domain,
            "visual_domain_fine": domain_fine,
            "visual_subdomain": subdomain,
            "source_video_category": raw_video_cat,
        },
        "metadata": {
            "original_row_id": row_id,
            "source_dataset": _clean(row.get("source_dataset")) or "youtube8m",
        },
    }
    return record, issues


def build_stats(records: List[Dict[str, Any]], jsonl_path: Path, inputs: Dict[str, str]) -> Dict[str, Any]:
    from collections import Counter

    def counts(key_fn):
        return dict(Counter(key_fn(r) for r in records).most_common())

    min_fps_vals = [r["temporal_requirements"]["min_fps"] for r in records]
    clip_durs = [r["time"]["clip_duration_sec"] for r in records]
    cert_durs = [r["time"]["temporal_certificate_duration_sec"] for r in records]
    video_ids = {r["source"]["video_id"] for r in records}
    urls = {r["source"]["url"] for r in records}

    sha = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()

    def fps_buckets():
        from collections import Counter as C
        return dict(C(min_fps_bucket(v) for v in min_fps_vals))

    def num_stats(vals):
        return {
            "count": len(vals),
            "min": min(vals),
            "max": max(vals),
            "mean": round(statistics.mean(vals), 4),
            "median": statistics.median(vals),
        }

    return {
        "num_examples": len(records),
        "num_unique_source_urls": len(urls),
        "num_unique_youtube_ids": len(video_ids),
        "paper_unique_video_count": PAPER_UNIQUE_VIDEO_COUNT,
        "unique_video_count_matches_paper": len(video_ids) == PAPER_UNIQUE_VIDEO_COUNT,
        "task_category_counts": counts(lambda r: r["question"]["type"]),
        "visual_domain_counts": counts(lambda r: r["categories"]["visual_domain"]),
        "visual_domain_fine_counts": counts(lambda r: r["categories"]["visual_domain_fine"]),
        "visual_subdomain_counts": counts(lambda r: r["categories"]["visual_subdomain"]),
        "min_fps": {**num_stats(min_fps_vals), "bucket_counts": fps_buckets()},
        "clip_duration_sec": num_stats(clip_durs),
        "temporal_certificate_duration_sec": num_stats(cert_durs),
        "availability_checked_utc": None,
        "sha256_jsonl": sha,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_inputs": inputs,
    }


def main():
    ap = argparse.ArgumentParser(description="Ingest FPS-Bench source spreadsheet into release artifacts.")
    ap.add_argument("--input-xlsx", required=True)
    ap.add_argument("--paper-pdf", default=None)
    ap.add_argument("--output-dir", default="annotations")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows = load_rows(args.input_xlsx)

    # Validate required columns.
    present = set(rows[0].keys()) if rows else set()
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in present]
    if missing_cols:
        print(f"ERROR: missing required columns: {missing_cols}", file=sys.stderr)
        sys.exit(2)

    records: List[Dict[str, Any]] = []
    all_issues: List[Issue] = []
    seen_ids = set()
    seen_row_ids = set()

    for row in rows:
        row_id = int(row["id"])
        if row_id in seen_row_ids:
            all_issues.append(Issue(row_id, "critical", "duplicate_original_row_id", "row id seen more than once", str(row_id)))
            continue
        seen_row_ids.add(row_id)
        rec, issues = build_record(row, args.version)
        all_issues.extend(issues)
        if rec is not None:
            if rec["id"] in seen_ids:
                all_issues.append(Issue(row_id, "critical", "duplicate_public_id", "public id collision", rec["id"]))
                continue
            seen_ids.add(rec["id"])
            records.append(rec)

    # Sort records by original row id for stable output.
    records.sort(key=lambda r: r["metadata"]["original_row_id"])

    # --- write artifacts ---
    # Published, questions-only canonical file (answer key stripped). The stats
    # hash below is taken over this file, since it is what users download.
    public_records = [fio.to_public_record(r) for r in records]
    jsonl_path = out / "fpsbench_v1.jsonl"
    fio.write_jsonl(jsonl_path, public_records)
    fio.write_csv(out / "fpsbench_v1.csv", public_records, public=True)
    (out / "fpsbench_v1.schema.json").write_text(
        json.dumps(fschema.build_json_schema(public=True), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Maintainer-only artifacts that carry the answer key. These are .gitignore'd
    # and never published; they back the held-out leaderboard's scoring.
    fio.write_jsonl(out / "fpsbench_v1.full.jsonl", records)
    fio.write_csv(out / "fpsbench_v1.full.csv", records)
    answer_records = [fio.to_answer_record(r) for r in records]
    fio.write_jsonl(out / "fpsbench_v1.answers.jsonl", answer_records)

    inputs = {"input_xlsx": Path(args.input_xlsx).name}
    if args.paper_pdf:
        inputs["paper_pdf"] = Path(args.paper_pdf).name
    stats = build_stats(records, jsonl_path, inputs)
    (out / "fpsbench_v1_stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    # Dataset-level unique-video-count mismatch (noncritical, documented).
    if not stats["unique_video_count_matches_paper"]:
        all_issues.append(Issue("(dataset)", "noncritical", "unique_video_count_mismatch",
                                f"released unique videos={stats['num_unique_youtube_ids']} vs paper={PAPER_UNIQUE_VIDEO_COUNT}",
                                ""))

    # --- readiness report ---
    n_critical = len({i.row_id for i in all_issues if i.severity == "critical"})
    n_noncritical = sum(1 for i in all_issues if i.severity == "noncritical")
    print("=" * 70)
    print("FPS-Bench release readiness report")
    print("=" * 70)
    print(f"Input rows loaded:            {len(rows)} (expected {EXPECTED_INPUT_ROWS})")
    print(f"Released examples:            {len(records)}")
    print(f"Excluded (critical issues):   {len(rows) - len(records)}")
    print(f"Unique YouTube IDs:           {stats['num_unique_youtube_ids']} (paper claims {PAPER_UNIQUE_VIDEO_COUNT})")
    print(f"Unique source URLs:           {stats['num_unique_source_urls']}")
    print(f"minFPS mean/median/min/max:   {stats['min_fps']['mean']}/{stats['min_fps']['median']}/{stats['min_fps']['min']}/{stats['min_fps']['max']}")
    print(f"Critical issues (rows):       {n_critical}")
    print(f"Noncritical issues (entries): {n_noncritical}")
    print("\nTask-category distribution:")
    for k, v in stats["task_category_counts"].items():
        print(f"  {k:30} {v}")
    print("\nVisual-domain distribution:")
    for k, v in stats["visual_domain_counts"].items():
        print(f"  {k:30} {v}")
    print(f"\nArtifacts written to: {out}/")
    print("  published (questions-only):")
    for name in ("fpsbench_v1.jsonl", "fpsbench_v1.csv",
                 "fpsbench_v1.schema.json", "fpsbench_v1_stats.json"):
        print(f"    - {name}")
    print("  maintainer-only (.gitignore'd, carries answers -- DO NOT publish):")
    for name in ("fpsbench_v1.full.jsonl", "fpsbench_v1.full.csv",
                 "fpsbench_v1.answers.jsonl"):
        print(f"    - {name}")

    noncritical = [i for i in all_issues if i.severity == "noncritical"]
    if noncritical:
        print(f"\nNoncritical notes ({len(noncritical)}) — kept in the release, see README 'Data quality':")
        for i in sorted(noncritical, key=lambda i: str(i.row_id)):
            print(f"  [{i.row_id}] {i.issue}: {i.detail}")
    if n_critical:
        print(f"\nNOTE: {n_critical} row(s) had critical issues and were EXCLUDED. "
              f"Final released count = {len(records)}.")
    print(f"\nsha256(fpsbench_v1.jsonl) = {stats['sha256_jsonl']}")


if __name__ == "__main__":
    main()
