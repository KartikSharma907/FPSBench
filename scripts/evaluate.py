#!/usr/bin/env python3
"""Run a model adapter over FPS-Bench and write the predictions.

This is the primary batch evaluation path. It loads an adapter by ``module:Class``
string, builds prompts (never leaking the answer), assembles the requested media
bundle, collects predictions, and writes a per-example JSONL plus a summary JSON.

The published ``fpsbench_v1.jsonl`` includes the answer key, so this scores the
predictions and reports accuracy. You can optionally submit the predictions file
to the leaderboard as well.

Example (random baseline, text-only, smoke test):
    python scripts/evaluate.py \
        --annotations annotations/fpsbench_v1.jsonl \
        --adapter fpsbench.adapters.random_baseline:RandomBaselineAdapter \
        --media-mode text-only --limit 20 \
        --output results/random_predictions.jsonl \
        --summary results/random_summary.json
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fpsbench import io as fio  # noqa: E402
from fpsbench import prompts as fprompts  # noqa: E402
from fpsbench.media import Media, expected_clip_path, extract_frames, default_cache_dir  # noqa: E402
from fpsbench.metrics import compute_metrics  # noqa: E402
from fpsbench.parsing import parse_answer  # noqa: E402


def load_adapter(spec: str, seed: int):
    """Import ``module:Class`` and instantiate it. Passes ``seed`` if accepted."""
    if ":" not in spec:
        raise ValueError("adapter must be 'module.path:ClassName'")
    mod_name, cls_name = spec.split(":", 1)
    cls = getattr(importlib.import_module(mod_name), cls_name)
    try:
        return cls(seed=seed)
    except TypeError:
        return cls()


def filter_records(records: List[Dict], args) -> List[Dict]:
    out = records
    if args.split:
        out = [r for r in out if r["split"] == args.split]
    if args.task_category:
        out = [r for r in out if r["question"]["type"] == args.task_category]
    if args.visual_domain:
        out = [r for r in out if r["categories"]["visual_domain"] == args.visual_domain]
    if args.min_fps_min is not None:
        out = [r for r in out if r["temporal_requirements"]["min_fps"] >= args.min_fps_min]
    if args.min_fps_max is not None:
        out = [r for r in out if r["temporal_requirements"]["min_fps"] <= args.min_fps_max]
    if args.ids:
        wanted = {line.strip() for line in Path(args.ids).read_text().splitlines() if line.strip()}
        out = [r for r in out if r["id"] in wanted]
    if args.limit:
        out = out[: args.limit]
    return out


def build_media(rec: Dict, args, manifest_index: Dict[str, Dict], cache_dir: Path) -> Media:
    if args.media_mode == "text-only":
        return Media()
    if args.media_mode == "source-url":
        return Media(source_url=rec["source"]["url"])

    local_path = None
    entry = manifest_index.get(rec["id"])
    if entry and entry.get("local_media_path") and Path(entry["local_media_path"]).exists():
        local_path = entry["local_media_path"]
    else:
        if args.window == "temporal_certificate":
            start, end = rec["time"]["temporal_certificate_start_sec"], rec["time"]["temporal_certificate_end_sec"]
        else:
            start, end = rec["time"]["clip_start_sec"], rec["time"]["clip_end_sec"]
        candidate = expected_clip_path(cache_dir, rec["id"], args.window, start, end)
        if candidate.exists():
            local_path = str(candidate)

    if args.media_mode == "video":
        return Media(local_video_path=local_path)

    # frames mode
    if not local_path:
        return Media()  # no local media; adapter sees text-only
    tfps = None
    if args.frame_sampling == "min_fps":
        tfps = float(rec["temporal_requirements"]["min_fps"])
    elif args.frame_sampling == "fixed_fps":
        tfps = args.fixed_fps
    frame_dir = cache_dir / "frames" / args.window / rec["id"]
    frames = extract_frames(local_path, frame_dir, strategy=args.frame_sampling,
                            target_fps=tfps, max_frames=args.max_frames)
    return Media(sampled_frames=frames, num_frames=len(frames))


def main():
    ap = argparse.ArgumentParser(description="Evaluate a model adapter on FPS-Bench.")
    ap.add_argument("--annotations", required=True)
    ap.add_argument("--adapter", required=True, help="module.path:ClassName")
    ap.add_argument("--prepared-manifest", default=None)
    ap.add_argument("--output", required=True)
    ap.add_argument("--summary", required=True)
    # selection
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ids", default=None)
    ap.add_argument("--task-category", default=None)
    ap.add_argument("--visual-domain", default=None)
    ap.add_argument("--min-fps-min", type=float, default=None)
    ap.add_argument("--min-fps-max", type=float, default=None)
    # media
    ap.add_argument("--media-mode", default="text-only", choices=["video", "frames", "text-only", "source-url"])
    ap.add_argument("--frame-sampling", default="min_fps", choices=["min_fps", "fixed_fps", "uniform"])
    ap.add_argument("--fixed-fps", type=float, default=2.0)
    ap.add_argument("--max-frames", type=int, default=512)
    ap.add_argument("--window", default="clip", choices=["clip", "temporal_certificate"])
    ap.add_argument("--cache-dir", default=None)
    # prompting
    ap.add_argument("--shuffle-options", action="store_true")
    ap.add_argument("--include-none-of-above", dest="include_none", action="store_true", default=True)
    ap.add_argument("--exclude-none-of-above", dest="include_none", action="store_false")
    ap.add_argument("--answer-parser", default="first_letter", choices=["strict", "first_letter", "llm_judge"])
    # run control
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--save-every", type=int, default=25)
    args = ap.parse_args()

    records = filter_records(fio.read_jsonl(args.annotations), args)
    adapter = load_adapter(args.adapter, args.seed)
    cache_dir = Path(args.cache_dir) if args.cache_dir else default_cache_dir()

    manifest_index: Dict[str, Dict] = {}
    if args.prepared_manifest and Path(args.prepared_manifest).exists():
        manifest_index = {e["id"]: e for e in fio.read_jsonl(args.prepared_manifest)}

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done_ids = set()
    results: List[Dict] = []
    if args.resume and out_path.exists():
        results = fio.read_jsonl(out_path)
        done_ids = {r["id"] for r in results}

    def flush():
        fio.write_jsonl(out_path, results)

    for i, rec in enumerate(records):
        if rec["id"] in done_ids:
            continue
        prompt, presented, letter_to_text = fprompts.build_prompt(
            rec, include_none_of_above=args.include_none,
            shuffle=args.shuffle_options, seed=args.seed,
        )
        example = {"id": rec["id"], "prompt": prompt, "presented_choices": presented,
                   "question": {"text": rec["question"]["text"]}}
        allowed = [l for l, _ in presented]
        media = build_media(rec, args, manifest_index, cache_dir)

        error = None
        try:
            resp = adapter.predict(example, media)
        except Exception as e:
            resp = {"prediction": None, "raw_response": "", "metadata": {}}
            error = str(e)[:300]

        raw = resp.get("raw_response", "")
        pred = resp.get("prediction")
        if pred is None and not error:
            pred = parse_answer(raw, allowed, mode=args.answer_parser)
        # Map a shuffled prediction back to the canonical answer letter.
        canonical_pred = pred
        if pred is not None and args.shuffle_options:
            text = letter_to_text.get(pred)
            for letter, ctext in rec["question"]["choices"].items():
                if ctext == text:
                    canonical_pred = letter
                    break

        # The published annotations include the answer key. ``.get`` keeps this
        # robust to a custom annotations file that happens to omit answers.
        correct_answer = rec["question"].get("answer")
        if canonical_pred is None or correct_answer is None:
            correct = None
        else:
            correct = canonical_pred == correct_answer

        results.append({
            "id": rec["id"],
            "prediction": canonical_pred,
            "correct_answer": correct_answer,
            "correct": correct,
            "raw_response": raw,
            "task_category": rec["question"]["type"],
            "visual_domain": rec["categories"]["visual_domain"],
            "visual_subdomain": rec["categories"]["visual_subdomain"],
            "min_fps": rec["temporal_requirements"]["min_fps"],
            "clip_duration_sec": rec["time"]["clip_duration_sec"],
            "media_mode": args.media_mode,
            "frame_sampling": args.frame_sampling if args.media_mode == "frames" else None,
            "num_frames": media.num_frames,
            "error": error,
        })
        if (i + 1) % args.save_every == 0:
            flush()

    flush()
    summary = compute_metrics(results)
    summary["adapter"] = args.adapter
    summary["media_mode"] = args.media_mode
    summary["num_examples"] = len(records)
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote {len(results)} predictions -> {out_path}")
    print(f"Overall accuracy: {summary['overall_accuracy']:.3f} "
          f"(random baseline {summary['random_baseline']:.2f}), "
          f"no-answer rate {summary['no_answer_rate']:.3f}")
    print(f"Summary -> {args.summary}")


if __name__ == "__main__":
    main()
