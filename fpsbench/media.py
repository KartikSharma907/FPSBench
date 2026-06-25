"""User-side media helpers: cache locations, clip windows, frame sampling.

Everything here operates on *local* files the user already has (or has lawfully
prepared). Nothing in this module downloads audiovisual content; that lives in
``scripts/prepare_dataset.py`` behind an explicit opt-in flag. Heavy
dependencies (ffmpeg, decord/opencv) are imported lazily so ``import fpsbench``
stays cheap.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

__all__ = [
    "Media",
    "default_cache_dir",
    "expected_clip_path",
    "ffmpeg_available",
    "clip_local_video",
    "sample_frame_indices",
    "extract_frames",
]


@dataclass
class Media:
    """Bundle of media references passed to an adapter's ``predict``.

    Exactly one of the fields is typically populated depending on media mode:

    * ``local_video_path``: path to a prepared local clip/video.
    * ``sampled_frames``: a list of frame file paths (frames mode).
    * ``source_url``: the original YouTube URL (source-url mode).
    * all ``None``: text-only mode.
    """

    local_video_path: Optional[str] = None
    sampled_frames: Optional[List[str]] = None
    source_url: Optional[str] = None
    num_frames: Optional[int] = None


def default_cache_dir() -> Path:
    """Resolve the cache directory: ``$FPSBENCH_CACHE`` or ``~/.cache/fpsbench``."""
    env = os.environ.get("FPSBENCH_CACHE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "fpsbench"


def _fmt_sec(x: float) -> str:
    """Compact, filename-safe seconds (``100.0`` -> ``100``, ``100.5`` -> ``100.5``)."""
    return f"{float(x):g}"


def expected_clip_path(
    cache_dir, example_id: str, window: str, start_sec: float, end_sec: float, ext: str = "mp4"
) -> Path:
    """Deterministic local path for a prepared clip of ``example_id``.

    The filename encodes the example id, the window, **and the exact time bounds**:
    ``<cache>/clips/<window>/<id>_<start>-<end>.<ext>``. Encoding the bounds is
    deliberate: a cached clip is only ever reused when the requested segment is
    byte-for-byte the same one. This prevents a whole class of bugs where the
    same source video, requested for a different time window, silently reuses a
    previously cached clip of the wrong segment.
    """
    tag = f"{_fmt_sec(start_sec)}-{_fmt_sec(end_sec)}"
    return Path(cache_dir) / "clips" / window / f"{example_id}_{tag}.{ext}"


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def clip_local_video(
    src: str,
    out_path,
    start_sec: float,
    end_sec: float,
    *,
    target_fps: Optional[float] = None,
    no_audio: bool = True,
    max_height: Optional[int] = None,
) -> Path:
    """Clip ``[start_sec, end_sec)`` from a local video using ffmpeg.

    Raises:
        RuntimeError: if ffmpeg is unavailable or the command fails.
    """
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg not found on PATH; install ffmpeg to clip videos")
    src = Path(src)
    out_path = Path(out_path)
    if src.resolve() == out_path.resolve():
        raise RuntimeError(
            f"refusing to clip a file in place (src == out): {out_path}; "
            "clip to a distinct path"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    vf = []
    if target_fps:
        vf.append(f"fps={target_fps}")
    if max_height:
        vf.append(f"scale=-2:'min({max_height},ih)'")

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start_sec), "-to", str(end_sec), "-i", str(src)]
    if vf:
        cmd += ["-vf", ",".join(vf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]
    cmd += ["-an"] if no_audio else []
    cmd += [str(out_path)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"ffmpeg clip failed: {result.stderr.strip()[:500]}")
    return out_path


def sample_frame_indices(
    total_frames: int,
    native_fps: float,
    *,
    strategy: str = "min_fps",
    target_fps: Optional[float] = None,
    max_frames: Optional[int] = None,
    start_sec: float = 0.0,
    end_sec: Optional[float] = None,
) -> List[int]:
    """Compute frame indices to sample from a clip.

    Strategies:
        * ``"min_fps"`` / ``"fixed_fps"``: sample at ``target_fps`` across the
          window (``target_fps`` should be set to min_fps for the min_fps mode).
        * ``"uniform"``: sample ``max_frames`` indices uniformly across the window.
    """
    if total_frames <= 0 or native_fps <= 0:
        return [0] if total_frames > 0 else []
    start_idx = max(0, int(round(start_sec * native_fps)))
    end_idx = total_frames - 1 if end_sec is None else min(total_frames - 1, int(round(end_sec * native_fps)))
    if end_idx < start_idx:
        end_idx = start_idx

    if strategy == "uniform":
        n = max_frames or 32
        if end_idx == start_idx:
            return [start_idx]
        step = (end_idx - start_idx) / max(1, n - 1)
        idxs = sorted({int(round(start_idx + step * i)) for i in range(n)})
        return idxs

    # FPS-based sampling.
    tfps = target_fps or native_fps
    step = max(1, int(round(native_fps / tfps))) if tfps < native_fps else 1
    idxs = list(range(start_idx, end_idx + 1, step))
    if max_frames and len(idxs) > max_frames:
        # Downsample uniformly to the cap.
        keep = [idxs[int(round(i * (len(idxs) - 1) / (max_frames - 1)))] for i in range(max_frames)]
        idxs = sorted(set(keep))
    return idxs


def extract_frames(
    video_path: str,
    out_dir,
    *,
    strategy: str = "min_fps",
    target_fps: Optional[float] = None,
    max_frames: Optional[int] = None,
    start_sec: float = 0.0,
    end_sec: Optional[float] = None,
    jpeg_quality: int = 90,
) -> List[str]:
    """Extract sampled JPEG frames from a local video using OpenCV.

    Returns the list of written frame paths. Raises ``RuntimeError`` if OpenCV is
    unavailable or the video cannot be opened.
    """
    try:
        import cv2  # type: ignore
    except ImportError as e:  # pragma: no cover - optional dep
        raise RuntimeError("opencv-python is required for frame extraction") from e

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video_path}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    native = cap.get(cv2.CAP_PROP_FPS) or 30.0

    indices = sample_frame_indices(
        total, native, strategy=strategy, target_fps=target_fps,
        max_frames=max_frames, start_sec=start_sec, end_sec=end_sec,
    )
    written: List[str] = []
    for i, frame_idx in enumerate(indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok:
            continue
        path = out_dir / f"frame_{i:04d}.jpg"
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        written.append(str(path))
    cap.release()
    return written
