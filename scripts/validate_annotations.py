#!/usr/bin/env python3
"""Validate a FPS-Bench annotations JSONL file.

Exits with status 0 only when there are zero *critical* errors. Noncritical
warnings (e.g. a temporal certificate slightly outside its clip) are reported
but do not fail validation.

Usage:
    python scripts/validate_annotations.py annotations/fpsbench_v1.jsonl
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fpsbench import io as fio  # noqa: E402
from fpsbench import schema as fschema  # noqa: E402
from fpsbench.youtube import is_valid_video_id  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Validate FPS-Bench annotations JSONL.")
    ap.add_argument("jsonl", help="path to a fpsbench JSONL (published or .full)")
    ap.add_argument("--show-warnings", action="store_true", help="print noncritical warnings too")
    ap.add_argument("--public", action="store_true",
                    help="force questions-only validation (answer key must be absent); "
                         "by default each record is auto-detected from whether it carries an answer")
    args = ap.parse_args()

    records = fio.read_jsonl(args.jsonl)
    n_critical = 0
    n_warning = 0
    seen_ids = set()
    seen_row_ids = set()
    video_ids = set()
    urls = set()

    for rec in records:
        rid = rec.get("id")
        if rid in seen_ids:
            print(f"CRITICAL [{rid}]: duplicate public id")
            n_critical += 1
        seen_ids.add(rid)
        orig = rec.get("metadata", {}).get("original_row_id")
        if orig in seen_row_ids:
            print(f"CRITICAL [{rid}]: duplicate original_row_id {orig}")
            n_critical += 1
        seen_row_ids.add(orig)

        vid = rec.get("source", {}).get("video_id")
        if not is_valid_video_id(vid):
            print(f"CRITICAL [{rid}]: invalid YouTube id {vid!r}")
            n_critical += 1
        video_ids.add(vid)
        urls.add(rec.get("source", {}).get("url"))

        # Published files are questions-only; auto-detect per record so the same
        # command validates either the public file or the maintainer .full file.
        is_public = args.public or ("answer" not in rec.get("question", {}))
        msgs = fschema.validate_record(rec, include_warnings=True, public=is_public)
        for m in msgs:
            if m.startswith("WARNING: "):
                n_warning += 1
                if args.show_warnings:
                    print(f"warning  [{rid}]: {m[len('WARNING: '):]}")
            else:
                n_critical += 1
                print(f"CRITICAL [{rid}]: {m}")

    print("-" * 60)
    print(f"records:            {len(records)}")
    print(f"unique public ids:  {len(seen_ids)}")
    print(f"unique youtube ids: {len(video_ids)}")
    print(f"unique source urls: {len(urls)}")
    print(f"critical errors:    {n_critical}")
    print(f"warnings:           {n_warning}" + ("" if args.show_warnings else "  (use --show-warnings to list)"))

    if n_critical:
        print("\nVALIDATION FAILED")
        sys.exit(1)
    print("\nVALIDATION PASSED (0 critical errors)")


if __name__ == "__main__":
    main()
