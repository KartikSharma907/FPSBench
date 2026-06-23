#!/usr/bin/env python3
"""Prepare a user's local evaluation environment from the public annotations.

Default behavior is SAFE and METADATA-ONLY: it never downloads audiovisual
content. Downloading clips requires the explicit ``--accept-source-terms`` flag
and prints a conspicuous warning. Users who already have lawful local copies
should prefer ``--mode local``.

Modes:
    manifest        (default) write a local manifest; no network.
    check           lightweight availability check; no AV download.
    local           match local videos by YouTube id (or a mapping CSV).
    download-clips  opt-in; download only the requested time windows.
    extract-frames  sample frames from already-local clips/videos.

Examples:
    python scripts/prepare_dataset.py \
        --annotations annotations/fpsbench_v1.jsonl \
        --output-dir data/fpsbench_v1 --mode manifest
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fpsbench import io as fio  # noqa: E402
from fpsbench import media as fmedia  # noqa: E402

WINDOWS = ("clip", "temporal_certificate")


def _window_bounds(rec: Dict, window: str):
    t = rec["time"]
    if window == "temporal_certificate":
        return t["temporal_certificate_start_sec"], t["temporal_certificate_end_sec"]
    return t["clip_start_sec"], t["clip_end_sec"]


def _resolve_target_fps(spec: str, rec: Dict) -> Optional[float]:
    if spec == "native":
        return None
    if spec == "min_fps":
        return float(rec["temporal_requirements"]["min_fps"])
    return float(spec)


def _base_entry(rec: Dict, window: str, cache_dir: Path) -> Dict:
    start, end = _window_bounds(rec, window)
    return {
        "id": rec["id"],
        "video_id": rec["source"]["video_id"],
        "source_url": rec["source"]["url"],
        "clip_start_sec": rec["time"]["clip_start_sec"],
        "clip_end_sec": rec["time"]["clip_end_sec"],
        "temporal_certificate_start_sec": rec["time"]["temporal_certificate_start_sec"],
        "temporal_certificate_end_sec": rec["time"]["temporal_certificate_end_sec"],
        "window": window,
        "window_start_sec": start,
        "window_end_sec": end,
        "expected_local_path": str(fmedia.expected_clip_path(cache_dir, rec["id"], window, start, end)),
        "status": "not_prepared",
    }


def mode_manifest(records, out_dir, cache_dir, window) -> Dict:
    entries = [_base_entry(r, window, cache_dir) for r in records]
    fio.write_jsonl(out_dir / "manifest.jsonl", entries)
    return {"mode": "manifest", "entries": len(entries), "downloaded": 0}


def mode_check(records, out_dir, cache_dir, window) -> Dict:
    """Lightweight availability check via yt-dlp metadata (no AV download)."""
    try:
        import yt_dlp  # type: ignore
    except ImportError:
        print("ERROR: yt-dlp is required for --mode check (pip install -e '.[download]')", file=sys.stderr)
        sys.exit(2)

    print("NOTE: availability on YouTube can change at any time; this is a snapshot.")
    checked = datetime.now(timezone.utc).isoformat()
    entries: List[Dict] = []
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "simulate": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        for r in records:
            entry = _base_entry(r, window, cache_dir)
            try:
                info = ydl.extract_info(r["source"]["url"], download=False)
                entry["available"] = True
                entry["native_fps"] = info.get("fps")
                entry["duration_sec"] = info.get("duration")
            except Exception as e:  # availability/network errors are expected
                entry["available"] = False
                entry["error"] = str(e)[:200]
            entry["availability_checked_utc"] = checked
            entries.append(entry)
    fio.write_jsonl(out_dir / "availability_manifest.jsonl", entries)
    n_avail = sum(1 for e in entries if e.get("available"))
    return {"mode": "check", "entries": len(entries), "available": n_avail, "checked_utc": checked}


def _load_local_index(local_dir: Optional[str], mapping_csv: Optional[str]) -> Dict[str, str]:
    """Build {video_id -> local path}. Mapping CSV columns: video_id,path."""
    index: Dict[str, str] = {}
    if mapping_csv:
        import csv

        with open(mapping_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("video_id") and row.get("path"):
                    index[row["video_id"].strip()] = row["path"].strip()
    if local_dir:
        from fpsbench.youtube import extract_video_id

        for p in Path(local_dir).rglob("*"):
            if p.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov"):
                vid = extract_video_id(p.stem) or p.stem
                index.setdefault(vid, str(p))
    return index


def mode_local(records, out_dir, cache_dir, window, args) -> Dict:
    index = _load_local_index(args.local_video_dir, args.mapping_csv)
    if not index:
        print("ERROR: --mode local needs --local-video-dir and/or --mapping-csv with matches", file=sys.stderr)
        sys.exit(2)
    entries: List[Dict] = []
    failed: List[Dict] = []
    n_ok = 0
    for r in records:
        entry = _base_entry(r, window, cache_dir)
        src = index.get(r["source"]["video_id"])
        if not src:
            entry["status"] = "missing_local_source"
            failed.append(entry)
            entries.append(entry)
            continue
        if args.clip:
            start, end = _window_bounds(r, window)
            try:
                out_path = fmedia.expected_clip_path(cache_dir, r["id"], window, start, end)
                fmedia.clip_local_video(src, out_path, start, end, no_audio=args.no_audio, max_height=args.max_height)
                entry["local_media_path"] = str(out_path)
                entry["status"] = "prepared"
                n_ok += 1
            except Exception as e:
                entry["status"] = "clip_failed"
                entry["error"] = str(e)[:200]
                failed.append(entry)
        else:
            entry["local_media_path"] = src
            entry["status"] = "matched"
            n_ok += 1
        entries.append(entry)
    fio.write_jsonl(out_dir / "manifest.jsonl", entries)
    if failed:
        fio.write_jsonl(out_dir / "failed.jsonl", failed)
    return {"mode": "local", "entries": len(entries), "ok": n_ok, "failed": len(failed)}


def mode_download_clips(records, out_dir, cache_dir, window, args) -> Dict:
    if not args.accept_source_terms:
        print(
            "\n" + "!" * 70 + "\n"
            "REFUSING TO DOWNLOAD: --mode download-clips requires --accept-source-terms.\n"
            "You are responsible for complying with YouTube's Terms of Service, the\n"
            "source licenses, copyright law, and your institution's policies. Downloaded\n"
            "clips are user-side artifacts and must NOT be redistributed.\n" + "!" * 70,
            file=sys.stderr,
        )
        sys.exit(2)

    print("\n" + "!" * 70)
    print("WARNING: downloading time windows from YouTube. This is YOUR responsibility")
    print("under YouTube ToS / source licenses / copyright / institutional policy.")
    print("Clips are written to a git-ignored cache and must not be redistributed.")
    print("!" * 70 + "\n")

    try:
        import yt_dlp  # type: ignore
    except ImportError:
        print("ERROR: yt-dlp required (pip install -e '.[download]')", file=sys.stderr)
        sys.exit(2)

    entries: List[Dict] = []
    failed: List[Dict] = []
    n_ok = 0
    todo = records[: args.limit] if args.limit else records

    for r in todo:
        entry = _base_entry(r, window, cache_dir)
        start, end = _window_bounds(r, window)
        # The cached clip is keyed on the exact canonical window, so a different
        # timestamp (or window) can never reuse this file.
        out_path = fmedia.expected_clip_path(cache_dir, r["id"], window, start, end)
        if args.resume and out_path.exists() and out_path.stat().st_size > 0:
            entry["status"] = "already_present"
            entry["local_media_path"] = str(out_path)
            n_ok += 1
            entries.append(entry)
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Download a (possibly padded) range to a distinct temp file, then trim to
        # the exact canonical window. Padding only gives ffmpeg keyframe slack; the
        # final clip is always exactly [start, end] regardless of --padding-sec.
        dl_start = max(0.0, start - args.padding_sec)
        dl_end = end + args.padding_sec
        tmp_tmpl = str(out_path.with_name(out_path.stem + ".download")) + ".%(ext)s"
        tfps = _resolve_target_fps(args.target_fps, r)
        opts = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": tmp_tmpl,
            "format": f"best[height<={args.max_height}]" if args.max_height else "best",
            "download_ranges": (lambda s, e: (lambda info, ydl: [{"start_time": s, "end_time": e}]))(dl_start, dl_end),
            "force_keyframes_at_cuts": True,
        }
        raw = None
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([r["source"]["url"]])
            raw = next(iter(out_path.parent.glob(f"{out_path.stem}.download.*")), None)
            if raw is None or not raw.exists() or raw.stat().st_size == 0:
                raise RuntimeError("yt-dlp produced no output for the requested range")
            # Trim the downloaded segment to the exact window (offset = how much
            # padding actually got prepended after clamping at 0) and apply
            # fps/audio/scale options. Always writes to a distinct out_path.
            offset = start - dl_start
            fmedia.clip_local_video(
                str(raw), out_path, offset, offset + (end - start),
                target_fps=tfps, no_audio=args.no_audio, max_height=args.max_height,
            )
            entry["status"] = "downloaded"
            entry["local_media_path"] = str(out_path)
            n_ok += 1
        except Exception as e:
            entry["status"] = "download_failed"
            entry["error"] = str(e)[:200]
            failed.append(entry)
        finally:
            if raw is not None and raw.exists():
                raw.unlink()  # never keep (or redistribute) the untrimmed download
        entries.append(entry)

    fio.write_jsonl(out_dir / "manifest.jsonl", entries)
    if failed:
        fio.write_jsonl(out_dir / "failed.jsonl", failed)
    return {"mode": "download-clips", "entries": len(entries), "ok": n_ok, "failed": len(failed)}


def mode_extract_frames(records, out_dir, cache_dir, window, args) -> Dict:
    print("NOTE: extracted frames are DERIVED MEDIA. Do not redistribute unless you "
          "have the rights to do so.")
    # Operate only on already-local clips found in the cache or a provided manifest.
    src_manifest = args.from_manifest
    index: Dict[str, str] = {}
    if src_manifest:
        for e in fio.read_jsonl(src_manifest):
            if e.get("local_media_path"):
                index[e["id"]] = e["local_media_path"]
    entries: List[Dict] = []
    failed: List[Dict] = []
    n_ok = 0
    for r in records:
        entry = _base_entry(r, window, cache_dir)
        start, end = _window_bounds(r, window)
        src = index.get(r["id"]) or str(fmedia.expected_clip_path(cache_dir, r["id"], window, start, end))
        if not Path(src).exists():
            entry["status"] = "no_local_clip"
            failed.append(entry)
            entries.append(entry)
            continue
        frame_dir = out_dir / "frames" / r["id"]
        tfps = _resolve_target_fps(args.target_fps, r) if args.frame_sampling != "uniform" else None
        try:
            frames = fmedia.extract_frames(
                src, frame_dir,
                strategy=args.frame_sampling, target_fps=tfps, max_frames=args.max_frames,
            )
            entry["status"] = "frames_extracted"
            entry["num_frames"] = len(frames)
            entry["frame_dir"] = str(frame_dir)
            n_ok += 1
        except Exception as e:
            entry["status"] = "extract_failed"
            entry["error"] = str(e)[:200]
            failed.append(entry)
        entries.append(entry)
    fio.write_jsonl(out_dir / "manifest.jsonl", entries)
    if failed:
        fio.write_jsonl(out_dir / "failed.jsonl", failed)
    return {"mode": "extract-frames", "entries": len(entries), "ok": n_ok, "failed": len(failed)}


def main():
    ap = argparse.ArgumentParser(description="Prepare FPS-Bench local environment (metadata-only by default).")
    ap.add_argument("--annotations", required=True)
    ap.add_argument("--output-dir", default="data/fpsbench_v1")
    ap.add_argument("--mode", default="manifest",
                    choices=["manifest", "check", "local", "download-clips", "extract-frames"])
    ap.add_argument("--window", default="clip", choices=list(WINDOWS))
    ap.add_argument("--cache-dir", default=None, help="defaults to $FPSBENCH_CACHE or ~/.cache/fpsbench")
    ap.add_argument("--limit", type=int, default=None)
    # local
    ap.add_argument("--local-video-dir", default=None)
    ap.add_argument("--mapping-csv", default=None, help="CSV with columns: video_id,path")
    ap.add_argument("--clip", action="store_true", help="(local mode) clip local videos to the window")
    # download-clips
    ap.add_argument("--accept-source-terms", action="store_true",
                    help="REQUIRED to enable any download; acknowledges YouTube ToS / licenses")
    ap.add_argument("--padding-sec", type=float, default=0.0)
    ap.add_argument("--target-fps", default="native", help="native | min_fps | 30 | FLOAT")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--max-height", type=int, default=None)
    ap.add_argument("--resume", action="store_true")
    # extract-frames
    ap.add_argument("--frame-sampling", default="min_fps", choices=["min_fps", "fixed_fps", "uniform"])
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--from-manifest", default=None, help="manifest.jsonl with local_media_path entries")
    args = ap.parse_args()

    records = fio.read_jsonl(args.annotations)
    if args.limit and args.mode in ("manifest", "check"):
        records = records[: args.limit]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(args.cache_dir) if args.cache_dir else fmedia.default_cache_dir()

    if args.mode == "manifest":
        summary = mode_manifest(records, out_dir, cache_dir, args.window)
    elif args.mode == "check":
        summary = mode_check(records, out_dir, cache_dir, args.window)
    elif args.mode == "local":
        summary = mode_local(records, out_dir, cache_dir, args.window, args)
    elif args.mode == "download-clips":
        summary = mode_download_clips(records, out_dir, cache_dir, args.window, args)
    else:
        summary = mode_extract_frames(records, out_dir, cache_dir, args.window, args)

    summary["cache_dir"] = str(cache_dir)
    summary["output_dir"] = str(out_dir)
    summary["generated_utc"] = datetime.now(timezone.utc).isoformat()
    (out_dir / "prepare_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
