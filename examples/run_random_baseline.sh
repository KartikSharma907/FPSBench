#!/usr/bin/env bash
# Run the random baseline (text-only) over the full benchmark and summarize.
set -euo pipefail
python scripts/evaluate.py \
  --annotations annotations/fpsbench_v1.jsonl \
  --adapter fpsbench.adapters.random_baseline:RandomBaselineAdapter \
  --media-mode text-only \
  --seed 42 \
  --output results/random_predictions.jsonl \
  --summary results/random_summary.json
