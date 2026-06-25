# FPS-Bench

**FPS-Bench is a benchmark for high-frame-rate video understanding.** It is a
multiple-choice video question-answering (VideoQA) benchmark designed to evaluate
fine-grained temporal perception and reasoning in video-language models — the
kinds of questions that *cannot* be answered from a handful of sparsely sampled
frames.

FPS-Bench introduces **minFPS** (minimum necessary frame rate): the lowest frame
rate at which a human annotator can consistently verify the correct answer.
Every question is curated to require a minFPS of at least 4, and the benchmark
spans **nine task categories** of rapid, high-frequency temporal phenomena.

> Paper: *FPS-Bench: A Benchmark for High Frame-Rate Video Understanding*
> (CVPR 2026), Carnegie Mellon University. Please cite it (see
> [CITATION.cff](CITATION.cff)) if you use this benchmark.

**Links:** [Project page](https://kartiksharma907.github.io/FPSBench/) ·
[Dataset (HuggingFace)](https://huggingface.co/datasets/Kartiksh/fpsbench) ·
[Leaderboard](https://huggingface.co/spaces/Kartiksh/fpsbench-leaderboard)

## What's in this release

This release contains **annotations and metadata, plus evaluation code** — it
does **not** contain any videos.

* **1,000 multiple-choice QA examples.** For each: a stable public ID, the
  YouTube video ID and URL, the clip and temporal-certificate time intervals, the
  question, four answer choices plus "None of the above", the correct answer, the
  **minFPS** label, the **nine-way task category**, and **visual-domain** labels.
* Canonical annotations in **JSONL**, a flattened **CSV** mirror, and a
  **JSON Schema** so you can validate your copy.
* A reusable Python package (`fpsbench/`) and CLI scripts for preparing media
  (user-side, opt-in), running evaluations, and scoring predictions.

**The release does NOT include** any videos, clips, extracted frames, thumbnails,
or cached media. You access the source videos yourself, under YouTube's Terms of
Service, the source licenses, copyright law, and your institution's policy (see
[Terms of use](#terms-of-use)).

## Repository layout

```
annotations/   fpsbench_v1.jsonl (canonical) + .csv mirror + .schema.json + _stats.json
fpsbench/      reusable library: schema, io, timestamps, categories, youtube, media,
               prompts, parsing, metrics, and adapters/ (base + random baseline)
scripts/       ingest / validate / prepare / evaluate / score CLIs
examples/      adapter template, example predictions, runnable shell scripts
tests/         pytest unit tests
```

## Install

The core library and evaluation/scoring path are **pure standard library** — no
required dependencies:

```bash
pip install -e .                 # installs the fpsbench-* console scripts
pip install -e ".[download]"     # + yt-dlp & opencv for user-side clip/frame prep
pip install -e ".[ingest]"       # + pandas & openpyxl to regenerate from the .xlsx
pip install -e ".[dev]"          # + pytest
```

## Quick start

```bash
# Validate the shipped annotations (must pass with 0 critical errors)
python scripts/validate_annotations.py annotations/fpsbench_v1.jsonl

# Build a metadata-only local manifest (NO download)
python scripts/prepare_dataset.py \
  --annotations annotations/fpsbench_v1.jsonl \
  --output-dir data/fpsbench_v1 --mode manifest

# Smoke-test evaluation with the random baseline (text-only)
python scripts/evaluate.py \
  --annotations annotations/fpsbench_v1.jsonl \
  --adapter fpsbench.adapters.random_baseline:RandomBaselineAdapter \
  --media-mode text-only --limit 20 \
  --output results/random_predictions.jsonl \
  --summary results/random_summary.json

# Score a precomputed predictions file (no model run)
python scripts/score_predictions.py \
  --annotations annotations/fpsbench_v1.jsonl \
  --predictions examples/predictions_template.jsonl \
  --summary results/template_summary.json
```

`examples/run_random_baseline.sh` and `examples/run_score_only.sh` wrap the last
two commands.

> **Answers are included.** The published `fpsbench_v1.jsonl` carries the answer
> key (`question.answer` / `answer_text`), so you can score and do error analysis
> locally. You can also submit your predictions to the
> [leaderboard](#leaderboard) to appear on the public table.

## Annotation schema

Canonical annotations are JSONL (one nested record per line). The CSV mirror is a
flattened view generated from the same records. Validate against
`annotations/fpsbench_v1.schema.json` (JSON Schema draft 2020-12) or with
`scripts/validate_annotations.py`, which also runs the cross-field checks below.

```json
{
  "id": "fpsbench_000000",
  "version": "1.0.0",
  "split": "test",
  "source": {
    "dataset": "youtube8m", "platform": "youtube",
    "video_id": "PhR5Dnuu_pg",
    "url": "https://www.youtube.com/watch?v=PhR5Dnuu_pg",
    "video_available_at_release": null, "availability_checked_utc": null
  },
  "time": {
    "clip_start_sec": 100.0, "clip_end_sec": 106.0, "clip_duration_sec": 6.0,
    "temporal_certificate_start_sec": 100.0, "temporal_certificate_end_sec": 104.0,
    "temporal_certificate_duration_sec": 4.0,
    "raw_clip_range": "1:40 - 1:46", "raw_temporal_certificate": "1:40-1:44"
  },
  "question": {
    "text": "How many dribbles does the player make?",
    "type": "repetitive_motion",
    "choices": {"A": "3", "B": "4", "C": "5", "D": "6", "E": "None of the above"},
    "answer": "A", "answer_text": "3"
  },
  "temporal_requirements": {
    "min_fps": 7, "min_required_frames_for_certificate": 28, "native_fps": null
  },
  "categories": {
    "task_category": "repetitive_motion", "visual_domain": "Sports & Fitness",
    "visual_domain_fine": "Sports & Fitness", "visual_subdomain": "Team Sports",
    "source_video_category": "Basketball"
  },
  "metadata": {"original_row_id": 0, "source_dataset": "youtube8m"}
}
```

The published `fpsbench_v1.jsonl` includes every field shown above, including
`question.answer` and `question.answer_text`.

Field notes:

- **`id`** — stable public ID `fpsbench_NNNNNN`; `metadata.original_row_id`
  preserves the original source row separately.
- **`question.type`** — the nine-way task category, lowercase snake_case:
  `repetitive_motion`, `speed_recognition`, `fine_grained_motion`, `action_order`,
  `state_at_event`, `blink_and_miss`, `causality_detection`,
  `synchronization_assessment`, `instance_count`.
- **`question.choices`** — keys are uppercase A–E (all string values). A–D are
  always present and non-empty; E, when present, is `"None of the above"`.
  `answer` is uppercase A–E and `answer_text` is the dereferenced choice text.
- **`temporal_requirements.min_fps`** — integer minimum necessary frame rate
  (≥ 4). `min_required_frames_for_certificate = round(min_fps ×
  temporal_certificate_duration_sec)`. `native_fps` is `null` (not measured at
  release; `prepare_dataset.py --mode check` can populate it per-user).
- **`categories.visual_domain`** — the paper-compatible five-way domain;
  `visual_domain_fine` / `visual_subdomain` give a finer taxonomy.

**Cross-field invariants** enforced by `validate_record`: clip/certificate
`start < end`; `answer` references an existing choice and `answer_text` matches
it; `min_fps ≥ 4`; no internal columns present. The internal source columns
`annotator`, `FPS Annotator 1`, and `media_S3_link` are **removed** and validation
rejects any record that carries them. (Certificate-contained-within-clip is a
*warning*, not a critical error — see [Data quality](#data-quality).)

## Preparing media (your responsibility, opt-in)

`scripts/prepare_dataset.py` is **safe and metadata-only by default**: the default
`--mode manifest` never touches the network. Prepared/derived media goes to a
cache directory (`--cache-dir` > `$FPSBENCH_CACHE` > `~/.cache/fpsbench`), never
under `annotations/` and never committed.

| mode | network | what it does |
|------|---------|--------------|
| `manifest` (default) | none | write a local manifest mapping each ID to its source/timestamps |
| `check` | metadata only | snapshot YouTube availability; writes `availability_manifest.jsonl` (needs `yt-dlp`) |
| `local` | none | match videos you already have by YouTube ID (or `--mapping-csv`), optionally `--clip` |
| `download-clips` | **opt-in** | download only the requested time windows; requires `--accept-source-terms` |
| `extract-frames` | none | sample frames from already-local clips (needs `opencv-python`) |

`local` (preferred for reproducibility) matches local videos by YouTube ID
inferred from the filename, or via `--mapping-csv` (columns `video_id,path`); with
`--clip` it cuts each to its window with ffmpeg. `download-clips` fetches only the
requested window (never full videos), **requires `--accept-source-terms`** (it
refuses and exits otherwise), and supports `--window {clip,temporal_certificate}`,
`--padding-sec`, `--target-fps {native,min_fps,30,FLOAT}`, `--no-audio`,
`--max-height`, `--limit`, `--resume`. All download/local/extract modes write
`manifest.jsonl` (+ `failed.jsonl`, `prepare_summary.json`).

**Clip caching.** Each prepared clip is cached at
`<cache>/clips/<window>/<id>_<start>-<end>.<ext>` — the filename encodes the exact
time window, so the *same source video requested for a different timestamp never
reuses a clip of the wrong segment*. Downloads are fetched to a temporary file and
trimmed to exactly the window, so `--padding-sec` only affects keyframe slack, not
the final clip. `--resume` only skips a clip when a non-empty file for that exact
window already exists.

## Evaluation

`scripts/evaluate.py` is the primary batch path. Implement the adapter interface
(`fpsbench/adapters/base.py`) and point `--adapter` at `module:Class`:

```python
class FPSBenchModel:
    def predict(self, example, media):
        # example: {"id", "prompt", "presented_choices", "question": {"text"}}  (NO answer)
        # media:   fpsbench.media.Media — local_video_path | sampled_frames | source_url | all None
        return {"prediction": "A", "raw_response": "...", "metadata": {}}
```

Return `prediction=None` to let the harness parse the letter from `raw_response`
using `--answer-parser {strict,first_letter,llm_judge}`. Built-in adapters:
`fpsbench.adapters.random_baseline:RandomBaselineAdapter` and an echo/debug
adapter; copy [examples/model_adapter_template.py](examples/model_adapter_template.py)
for your own model.

**Prompting protocol.** The model receives the question, the answer choices, and
(optionally) media. It **never** receives the correct answer, the answer text, the
minFPS, or the temporal certificate. Default system prompt:

> Analyze the video carefully, focusing on rapid motion and fine-grained temporal
> details. Answer the multiple-choice question. Start your response with exactly
> one option letter from the available choices, then provide a brief explanation.

Selection flags: `--split`, `--limit`, `--ids`, `--task-category`,
`--visual-domain`, `--min-fps-min/max`. Media: `--media-mode
{video,frames,text-only,source-url}`, `--frame-sampling {min_fps,fixed_fps,
uniform}`, `--fixed-fps`, `--max-frames`, `--window {clip,temporal_certificate}`.
Prompting: `--shuffle-options` (predictions are mapped back to the canonical
letter via choice text), `--exclude-none-of-above`. Run control: `--resume`,
`--save-every`.

**Metrics** (`fpsbench.metrics.compute_metrics`, also used by
`score_predictions.py`): overall exact-match accuracy with a 95% bootstrap CI, the
random baseline reference (0.20), accuracy by task category / visual domain /
visual subdomain / minFPS bucket (4, 5, 6, 7, 8–10, 10+) / clip-duration bucket,
the no-answer/invalid rate, and per-group counts.

Prediction file schema (JSONL) for `score_predictions.py`:
`{"id": "fpsbench_000000", "prediction": "A", "raw_response": "A. ..."}`. If
`prediction` is absent it is parsed from `raw_response`.

## Leaderboard

The answer key is included, so you score locally with `score_predictions.py`. To
also appear on the public leaderboard:

1. Run your model with `scripts/evaluate.py` over all 1000 examples to produce a
   predictions JSONL.
2. Upload that file to the leaderboard Space, which computes your metrics and adds
   you to the table.

➡️ **Leaderboard:** https://huggingface.co/spaces/Kartiksh/fpsbench-leaderboard

The Space uses the same scoring code path as `scripts/score_predictions.py`
(`score_predictions()`), reporting overall accuracy with a 95% bootstrap CI plus
per-task / per-domain / per-minFPS breakdowns. The leaderboard source lives in
[`leaderboard/`](leaderboard/). Because the answers are public, leaderboard
numbers are self-reported.

## Dataset statistics

* Examples: **1,000** &nbsp;|&nbsp; unique YouTube videos: **592** &nbsp;|&nbsp; unique URLs: **592**
* minFPS: min 4, max 30, mean **6.68**, median 6
  (buckets — 4: 254, 5: 209, 6: 153, 7: 133, 8–10: 158, 10+: 93)
* Clip duration (s): mean 8.85, median 9 &nbsp;|&nbsp; certificate duration (s): mean 4.99, median 4

**Task categories:** instance_count 117, repetitive_motion 113,
synchronization_assessment 111, speed_recognition 110, fine_grained_motion 110,
action_order 110, state_at_event 110, causality_detection 110, blink_and_miss 109.

**Visual domains (paper five-way):** Sports & Fitness 374, Hobbies & Gaming 191,
Media & Entertainment 178, Miscellaneous 168, Vehicles 89.

Full machine-readable stats: [annotations/fpsbench_v1_stats.json](annotations/fpsbench_v1_stats.json).

## Terms of use

These terms are in addition to the [LICENSE](LICENSE) (which covers only the
annotation metadata and code).

1. **No source videos are redistributed.** This release ships annotations and
   metadata only — video IDs, URLs, and time intervals, with no media.
2. **Source videos remain governed by their rights holders and YouTube's terms.**
   Videos were sourced from YouTube (via YouTube-8M). Your access to and use of
   them is subject to YouTube's Terms of Service, the videos' individual licenses,
   copyright law, and your institution's policies. You are solely responsible for
   lawful use.
3. **Any local clips or frames you generate are user-side artifacts** and must not
   be redistributed unless you independently hold the rights. The cache/output
   directories produced by `prepare_dataset.py` are git-ignored for this reason.
4. **The optional downloader is for user-side setup only.** The `download-clips`
   and `extract-frames` modes are disabled by default and require the explicit
   `--accept-source-terms` flag; using them grants no rights to the content.
5. **No availability or fitness warranty.** Videos may become unavailable at any
   time; the annotations and code are provided "as is" (see [LICENSE](LICENSE)).

By using this release you agree to these terms.
