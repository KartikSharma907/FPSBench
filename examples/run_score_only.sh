#!/usr/bin/env bash
# Score a precomputed predictions file without running any model.
#
# NOTE: scoring needs the answer key, which is held out of the public release.
# This requires the maintainer-only `fpsbench_v1.full.jsonl` (regenerated locally
# via scripts/ingest_release.py). Public users instead submit predictions to the
# leaderboard, which scores server-side against the private answers.
set -euo pipefail
python scripts/score_predictions.py \
  --annotations annotations/fpsbench_v1.full.jsonl \
  --predictions examples/predictions_template.jsonl \
  --summary results/template_summary.json \
  --scored-output results/template_scored.jsonl
