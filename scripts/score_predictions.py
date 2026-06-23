#!/usr/bin/env python3
"""Score a precomputed predictions file against the annotations (no model run).

Prediction file is JSONL, one object per line:
    {"id": "fpsbench_000000", "prediction": "A", "raw_response": "A. ..."}
or, when only free text is available:
    {"id": "fpsbench_000000", "raw_response": "I think the answer is B because ..."}

In the latter case the selected ``--answer-parser`` extracts the letter.

Scoring requires the answer key, which is held out of the public release. Pass
the maintainer-only ``fpsbench_v1.full.jsonl`` (or any annotations file that
carries ``question.answer``). Public users instead submit predictions to the
leaderboard, which runs this same scoring server-side against the private
answers.

Usage:
    python scripts/score_predictions.py \
        --annotations annotations/fpsbench_v1.full.jsonl \
        --predictions results/my_predictions.jsonl \
        --summary results/my_summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fpsbench import io as fio  # noqa: E402
from fpsbench.metrics import compute_metrics  # noqa: E402
from fpsbench.parsing import parse_answer  # noqa: E402


def score_predictions(annotations, predictions, *, answer_parser="first_letter"):
    """Score predictions against annotations and return ``(summary, scored_rows)``.

    ``annotations`` and ``predictions`` are each either a path to a JSONL file or
    an already-loaded list of dict records. ``annotations`` must carry the answer
    key (``question.answer``) -- i.e. the maintainer-only ``fpsbench_v1.full.jsonl``
    or the private answer set, never the published questions-only file. This is
    the single scoring code path shared by the CLI below and the leaderboard.
    """
    ann_records = fio.read_jsonl(annotations) if isinstance(annotations, (str, Path)) else annotations
    pred_records = fio.read_jsonl(predictions) if isinstance(predictions, (str, Path)) else predictions
    ann = {r["id"]: r for r in ann_records}

    rows = []
    n_missing = 0
    for p in pred_records:
        rec = ann.get(p.get("id"))
        if rec is None:
            n_missing += 1
            continue
        q = rec["question"]
        if "answer" not in q:
            raise ValueError(
                "annotations carry no answer key; scoring needs fpsbench_v1.full.jsonl "
                "(the published fpsbench_v1.jsonl is questions-only)"
            )
        allowed = list(q["choices"].keys())
        pred = p.get("prediction")
        if pred is None:
            pred = parse_answer(p.get("raw_response", ""), allowed, mode=answer_parser)
        if pred is not None:
            pred = str(pred).strip().upper()
        correct_answer = q["answer"]
        correct = None if pred not in allowed else (pred == correct_answer)
        rows.append({
            "id": rec["id"],
            "prediction": pred,
            "correct_answer": correct_answer,
            "correct": correct,
            "raw_response": p.get("raw_response", ""),
            "task_category": q["type"],
            "visual_domain": rec["categories"]["visual_domain"],
            "visual_subdomain": rec["categories"]["visual_subdomain"],
            "min_fps": rec["temporal_requirements"]["min_fps"],
            "clip_duration_sec": rec["time"]["clip_duration_sec"],
        })

    summary = compute_metrics(rows)
    summary["num_predictions"] = len(pred_records)
    summary["num_unmatched_ids"] = n_missing
    return summary, rows


def main():
    ap = argparse.ArgumentParser(description="Score precomputed FPS-Bench predictions.")
    ap.add_argument("--annotations", required=True)
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--scored-output", default=None, help="optional per-row scored JSONL")
    ap.add_argument("--answer-parser", default="first_letter", choices=["strict", "first_letter"])
    args = ap.parse_args()

    try:
        summary, rows = score_predictions(
            args.annotations, args.predictions, answer_parser=args.answer_parser
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    n_missing = summary["num_unmatched_ids"]

    if args.scored_output:
        fio.write_jsonl(args.scored_output, rows)

    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Scored {len(rows)} predictions ({n_missing} ids not found in annotations)")
    print(f"Overall accuracy: {summary['overall_accuracy']:.3f} "
          f"(random {summary['random_baseline']:.2f}), no-answer {summary['no_answer_rate']:.3f}")
    print(f"Summary -> {args.summary}")


if __name__ == "__main__":
    main()
