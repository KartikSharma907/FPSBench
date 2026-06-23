---
license: cc-by-sa-4.0
language:
- en
task_categories:
- visual-question-answering
- video-text-to-text
tags:
- video
- temporal-reasoning
- high-frame-rate
- videoqa
- benchmark
- minfps
pretty_name: FPS-Bench
size_categories:
- n<1K
configs:
- config_name: default
  data_files:
  - split: test
    path: fpsbench_v1.jsonl
---

# FPS-Bench

**A benchmark for high-frame-rate video understanding** (CVPR 2026, Carnegie
Mellon University). FPS-Bench is a 1,000-example multiple-choice VideoQA benchmark
targeting fine-grained temporal perception — questions that *cannot* be answered
from a handful of sparsely sampled frames.

It introduces **minFPS** (minimum necessary frame rate): the lowest frame rate at
which a human can consistently verify the answer (every question requires
minFPS ≥ 4), across **nine task categories** of rapid temporal phenomena.

- 📄 Project page: https://kartiksharma907.github.io/FPSBench/
- 💻 Code & evaluation harness: https://github.com/KartikSharma907/FPSBench
- 🏆 Leaderboard (held-out scoring): https://huggingface.co/spaces/YOUR-HF-USERNAME/fpsbench-leaderboard

## ⚠️ Held-out answers

This dataset is **questions-only**: it does **not** contain the answer key. To get
a score, run your model to produce predictions and submit them to the
[leaderboard](https://huggingface.co/spaces/YOUR-HF-USERNAME/fpsbench-leaderboard),
which scores server-side against the private answers. See the
[code repo](https://github.com/KartikSharma907/FPSBench) for the evaluation harness.

## No videos are redistributed

The release contains **annotations only** — no videos, clips, frames, or
thumbnails. Each record points to a public YouTube source `url` with `clip` and
`temporal_certificate` time spans. Access the source videos yourself under
YouTube's Terms of Service, the source licenses, and your institution's policy.
The repo's `scripts/prepare_dataset.py` (opt-in, `--accept-source-terms`) helps
you fetch the exact clips locally.

## Record schema

Each line of `fpsbench_v1.jsonl` is one example (`split: test`). Nested fields:

- `id`, `version`, `split`
- `source`: `{dataset, platform, video_id, url}`
- `time`: `clip_*` and `temporal_certificate_*` start/end/duration seconds (+ raw strings)
- `question`: `{text, type, choices{A..E}}` — **no `answer`** (held out)
- `temporal_requirements`: `{min_fps, min_required_frames_for_certificate, native_fps}`
- `categories`: `{task_category, visual_domain, visual_domain_fine, visual_subdomain, source_video_category}`
- `metadata`: `{original_row_id, source_dataset}`

The full JSON Schema is in `fpsbench_v1.schema.json`; aggregate statistics are in
`fpsbench_v1_stats.json`. A flattened CSV mirror is `fpsbench_v1.csv`.

## Load it

```python
from datasets import load_dataset
ds = load_dataset("YOUR-HF-USERNAME/fpsbench", split="test")
print(ds[0]["question"]["text"])
```

## Statistics

1,000 examples over 592 unique source videos; nine roughly balanced task
categories; minFPS mean ≈ 6.7 (min 4, max 30); clip duration mean ≈ 8.9 s.

## Citation

See `CITATION.cff` in the [code repository](https://github.com/KartikSharma907/FPSBench).
Licensed CC BY-SA 4.0 (annotations).
