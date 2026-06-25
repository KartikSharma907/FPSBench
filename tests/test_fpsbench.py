"""FPS-Bench unit tests (timestamps, schema, answer parsing, metrics, youtube,
media cache paths). Run with ``pytest`` from the repo root."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpsbench.timestamps import TimestampError, parse_interval, parse_timestamp
from fpsbench.schema import build_json_schema, validate_record
from fpsbench.parsing import parse_answer
from fpsbench.metrics import compute_metrics, min_fps_bucket
from fpsbench.youtube import extract_video_id, is_valid_video_id
from fpsbench.media import expected_clip_path, clip_local_video


# --------------------------------------------------------------------------- #
# timestamps
# --------------------------------------------------------------------------- #
def test_single_timestamps():
    assert parse_timestamp("1:40") == 100.0
    assert parse_timestamp("0:08") == 8.0
    assert parse_timestamp("12:32") == 752.0
    assert parse_timestamp("1:02:03") == 3723.0  # H:MM:SS


def test_range_with_and_without_spaces():
    a = parse_interval("1:40-1:44")
    assert (a.start_sec, a.end_sec) == (100.0, 104.0)
    assert a.duration_sec == 4.0
    b = parse_interval("1:40 - 1:46")
    assert (b.start_sec, b.end_sec) == (100.0, 106.0)
    assert b.raw == "1:40 - 1:46"


def test_known_repairs():
    p = parse_interval("0:49-0.53")
    assert p.repaired is True and (p.start_sec, p.end_sec) == (49.0, 53.0) and p.notes
    q = parse_interval("0:19:0:21")
    assert q.repaired is True and (q.start_sec, q.end_sec) == (19.0, 21.0)


@pytest.mark.parametrize("bad", ["", "   ", "abc", "1:60-2:00", "1:2:3:4:5", "1::2"])
def test_malformed_flagged(bad):
    with pytest.raises(TimestampError):
        parse_interval(bad)


def test_seconds_out_of_range():
    with pytest.raises(TimestampError):
        parse_timestamp("1:75")


# --------------------------------------------------------------------------- #
# schema
# --------------------------------------------------------------------------- #
def _valid_record():
    return {
        "id": "fpsbench_000000",
        "version": "1.0.0",
        "split": "test",
        "source": {
            "dataset": "youtube8m", "platform": "youtube",
            "video_id": "PhR5Dnuu_pg",
            "url": "https://www.youtube.com/watch?v=PhR5Dnuu_pg",
            "video_available_at_release": None, "availability_checked_utc": None,
        },
        "time": {
            "clip_start_sec": 100.0, "clip_end_sec": 106.0, "clip_duration_sec": 6.0,
            "temporal_certificate_start_sec": 100.0, "temporal_certificate_end_sec": 104.0,
            "temporal_certificate_duration_sec": 4.0,
            "raw_clip_range": "1:40 - 1:46", "raw_temporal_certificate": "1:40-1:44",
        },
        "question": {
            "text": "How many dribbles does the player make?",
            "type": "repetitive_motion",
            "choices": {"A": "3", "B": "4", "C": "5", "D": "6", "E": "None of the above"},
            "answer": "A", "answer_text": "3",
        },
        "temporal_requirements": {
            "min_fps": 7, "min_required_frames_for_certificate": 28, "native_fps": None,
        },
        "categories": {
            "task_category": "repetitive_motion", "visual_domain": "Sports & Fitness",
            "visual_domain_fine": "Sports & Fitness", "visual_subdomain": "Team Sports",
            "source_video_category": "Basketball",
        },
        "metadata": {"original_row_id": 0, "source_dataset": "youtube8m"},
    }


def test_valid_record_passes():
    assert validate_record(_valid_record()) == []


def test_json_schema_buildable():
    s = build_json_schema()
    assert s["title"] == "FPS-Bench annotation record" and "properties" in s


def test_public_schema_drops_answer_from_required():
    s = build_json_schema(public=True)
    req = s["properties"]["question"]["required"]
    assert "answer" not in req and "answer_text" not in req
    assert "text" in req and "choices" in req


# --------------------------------------------------------------------------- #
# public / private (held-out answer) split
# --------------------------------------------------------------------------- #
def test_to_public_record_strips_answer():
    from fpsbench import io as fio

    pub = fio.to_public_record(_valid_record())
    assert "answer" not in pub["question"]
    assert "answer_text" not in pub["question"]
    # everything else is preserved and the source is untouched
    assert pub["question"]["choices"]["A"] == "3"
    assert _valid_record()["question"]["answer"] == "A"  # original not mutated


def test_to_answer_record_keeps_only_answer():
    from fpsbench import io as fio

    ans = fio.to_answer_record(_valid_record())
    assert ans == {"id": "fpsbench_000000", "answer": "A", "answer_text": "3"}


def test_public_record_validates_in_public_mode_and_fails_strict():
    from fpsbench import io as fio

    pub = fio.to_public_record(_valid_record())
    assert validate_record(pub, public=True) == []
    # strict (default) mode must flag the missing answer key
    assert any("answer" in e for e in validate_record(pub))


def test_public_validation_rejects_leaked_answer():
    r = _valid_record()  # still carries answer/answer_text
    msgs = validate_record(r, public=True)
    assert any("leaks question.answer" in m for m in msgs)


def test_missing_min_fps_fails():
    r = _valid_record(); r["temporal_requirements"]["min_fps"] = None
    assert any("min_fps" in e for e in validate_record(r))


def test_min_fps_below_floor_fails():
    r = _valid_record(); r["temporal_requirements"]["min_fps"] = 2
    assert any("floor" in e for e in validate_record(r))


def test_invalid_answer_fails():
    r = _valid_record(); r["question"]["answer"] = "Z"
    assert any("answer" in e for e in validate_record(r))


def test_answer_not_referencing_choice_fails():
    r = _valid_record(); r["question"]["answer"] = "E"  # E exists but text won't match
    assert any("answer_text" in e for e in validate_record(r))


def test_malformed_times_fail():
    r = _valid_record(); r["time"]["clip_start_sec"] = 200.0  # start > end
    assert any("clip_start_sec" in e for e in validate_record(r))


def test_certificate_outside_clip_is_warning_not_critical():
    r = _valid_record()
    r["time"]["temporal_certificate_end_sec"] = 120.0
    r["time"]["temporal_certificate_duration_sec"] = 20.0
    assert validate_record(r) == []  # no critical error
    assert any("WARNING" in e for e in validate_record(r, include_warnings=True))


def test_banned_internal_fields_fail():
    r = _valid_record(); r["annotator"] = "JS"
    assert any("banned" in e for e in validate_record(r))


def test_missing_choice_fails():
    r = _valid_record(); del r["question"]["choices"]["C"]
    assert any("choices.C" in e for e in validate_record(r))


# --------------------------------------------------------------------------- #
# answer parsing
# --------------------------------------------------------------------------- #
def test_bare_and_leading_letter():
    assert parse_answer("A") == "A"
    assert parse_answer("A. The player dribbles three times.") == "A"
    assert parse_answer("(B) because ...") == "B"
    assert parse_answer("**C** - the flash is visible") == "C"


def test_answer_is_phrase():
    assert parse_answer("I think the answer is B because the motion repeats.") == "B"
    assert parse_answer("My choice would be option D.") == "D"


def test_invalid_free_text_returns_none():
    assert parse_answer("It is impossible to tell from the video.") is None
    assert parse_answer("") is None
    assert parse_answer(None) is None


def test_strict_mode_requires_leading_letter():
    assert parse_answer("The answer is B", mode="strict") is None
    assert parse_answer("B is correct", mode="strict") == "B"


def test_respects_allowed_letters():
    assert parse_answer("E none of the above", allowed_letters=["A", "B", "C", "D"]) is None


def test_does_not_match_indefinite_article():
    assert parse_answer("This is a hard question to answer.") is None


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def _rows():
    return [
        {"prediction": "A", "correct": True, "task_category": "repetitive_motion",
         "visual_domain": "Sports & Fitness", "visual_subdomain": "Team Sports",
         "min_fps": 4, "clip_duration_sec": 6.0},
        {"prediction": "B", "correct": False, "task_category": "repetitive_motion",
         "visual_domain": "Sports & Fitness", "visual_subdomain": "Team Sports",
         "min_fps": 8, "clip_duration_sec": 6.0},
        {"prediction": "C", "correct": True, "task_category": "instance_count",
         "visual_domain": "Vehicles", "visual_subdomain": "Ground Vehicles",
         "min_fps": 12, "clip_duration_sec": 3.0},
        {"prediction": None, "correct": None, "task_category": "instance_count",
         "visual_domain": "Vehicles", "visual_subdomain": "Ground Vehicles",
         "min_fps": 6, "clip_duration_sec": 3.0},
    ]


def test_overall_accuracy():
    m = compute_metrics(_rows(), bootstrap=False)
    assert m["num_scored"] == 3
    assert abs(m["overall_accuracy"] - (2 / 3)) < 1e-9


def test_per_category_accuracy():
    m = compute_metrics(_rows(), bootstrap=False)
    cat = m["accuracy_by_task_category"]
    assert cat["repetitive_motion"]["count"] == 2
    assert abs(cat["repetitive_motion"]["accuracy"] - 0.5) < 1e-9
    assert cat["instance_count"]["count"] == 1
    assert cat["instance_count"]["accuracy"] == 1.0


def test_invalid_answer_rate():
    m = compute_metrics(_rows(), bootstrap=False)
    assert m["num_invalid_or_no_answer"] == 1
    assert abs(m["no_answer_rate"] - 0.25) < 1e-9


def test_min_fps_buckets():
    assert min_fps_bucket(4) == "4"
    assert min_fps_bucket(7) == "7"
    assert min_fps_bucket(9) == "8-10"
    assert min_fps_bucket(30) == "10+"


def test_bootstrap_ci_present():
    m = compute_metrics(_rows(), bootstrap=True)
    lo, hi = m["overall_accuracy_95ci"]
    assert 0.0 <= lo <= hi <= 1.0


# --------------------------------------------------------------------------- #
# youtube
# --------------------------------------------------------------------------- #
def test_video_id_extraction():
    assert extract_video_id("https://www.youtube.com/watch?v=PhR5Dnuu_pg") == "PhR5Dnuu_pg"
    assert extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ&t=30s") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ?t=10") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_video_id_invalid():
    assert extract_video_id("https://example.com/video") is None
    assert extract_video_id("") is None
    assert extract_video_id(None) is None
    assert is_valid_video_id("dQw4w9WgXcQ")
    assert not is_valid_video_id("short")
    assert not is_valid_video_id(None)


# --------------------------------------------------------------------------- #
# media cache paths (regression test for the timestamp/cache bug)
# --------------------------------------------------------------------------- #
def test_clip_path_encodes_window_bounds():
    # Same video/example id but different time windows must map to DIFFERENT files,
    # so a cached clip is never reused for the wrong segment.
    a = expected_clip_path("/cache", "fpsbench_000063", "clip", 22.0, 26.0)
    b = expected_clip_path("/cache", "fpsbench_000063", "clip", 27.0, 37.0)
    assert a != b
    assert a.name == "fpsbench_000063_22-26.mp4"
    assert b.name == "fpsbench_000063_27-37.mp4"
    # The same bounds are stable (so --resume can match).
    assert a == expected_clip_path("/cache", "fpsbench_000063", "clip", 22.0, 26.0)
    # The clip and temporal_certificate windows are separated by directory.
    cert = expected_clip_path("/cache", "fpsbench_000063", "temporal_certificate", 22.0, 26.0)
    assert cert.parent.name == "temporal_certificate" and a.parent.name == "clip"


def test_clip_local_video_refuses_in_place(tmp_path):
    if not __import__("shutil").which("ffmpeg"):
        pytest.skip("ffmpeg not available")
    src = tmp_path / "v.mp4"
    src.write_bytes(b"not a real video")  # guard fires before ffmpeg runs
    with pytest.raises(RuntimeError, match="in place"):
        clip_local_video(str(src), str(src), 0.0, 1.0)
