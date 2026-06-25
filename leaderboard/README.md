---
title: FPS-Bench Leaderboard
emoji: 🎬
colorFrom: indigo
colorTo: yellow
sdk: gradio
sdk_version: 5.45.0
python_version: "3.12"
app_file: app.py
pinned: false
license: cc-by-sa-4.0
---

# FPS-Bench Leaderboard

A held-out-answer leaderboard for [FPS-Bench](https://github.com/KartikSharma907/FPSBench),
a benchmark for high-frame-rate video understanding.

The public dataset is **questions-only**. To get a score, run your model with
`scripts/evaluate.py` to produce a predictions JSONL, then upload it here — the
Space scores it server-side against the private answer key and appends the result
to the leaderboard.

## Deploying this Space

This directory is versioned in the main repo under `leaderboard/`. To deploy:

1. Create a **private** dataset `…/fpsbench-answers` containing
   `fpsbench_v1.full.jsonl` (the maintainer file with answers), and a dataset
   `…/fpsbench-leaderboard-results` for persisted submissions.
2. Create a Gradio Space and push the contents of this `leaderboard/` folder.
3. Set these Space **Secrets / Variables**:
   - `HF_TOKEN` — read access to the answers repo, write access to the results repo.
   - `FPSBENCH_ANSWERS_REPO` — e.g. `your-user/fpsbench-answers`.
   - `FPSBENCH_RESULTS_REPO` — e.g. `your-user/fpsbench-leaderboard-results`.

Without these, the app falls back to a local `annotations/fpsbench_v1.full.jsonl`
and a local `results.jsonl` for development.

## Submission format

JSONL covering all 1000 examples, one object per line:

```json
{"id": "fpsbench_000000", "prediction": "A"}
{"id": "fpsbench_000001", "raw_response": "I think the answer is B because ..."}
```

Scoring uses the same code path as the CLI (`scripts/score_predictions.py`):
overall accuracy with a 95% bootstrap CI, plus per-task / per-domain / per-minFPS
breakdowns.
