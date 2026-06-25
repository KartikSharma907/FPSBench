#!/usr/bin/env bash
# Score a precomputed predictions file without running any model.
# The published annotations include the answer key, so this scores locally.
set -euo pipefail
python scripts/score_predictions.py \
  --annotations annotations/fpsbench_v1.jsonl \
  --predictions examples/predictions_template.jsonl \
  --summary results/template_summary.json \
  --scored-output results/template_scored.jsonl
