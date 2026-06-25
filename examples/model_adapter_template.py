"""Template adapter you can copy and edit for your own model.

Run it with:
    python scripts/evaluate.py \
        --annotations annotations/fpsbench_v1.jsonl \
        --adapter examples.model_adapter_template:MyModel \
        --media-mode text-only --limit 20 \
        --output results/mymodel_predictions.jsonl \
        --summary results/mymodel_summary.json

The harness builds the prompt and the media bundle for you. Your job is to send
them to your model and return ``{"prediction", "raw_response", "metadata"}``. If
you return ``prediction=None``, the harness parses the letter from
``raw_response`` using the configured ``--answer-parser``.
"""

from __future__ import annotations

from typing import Any, Dict

from fpsbench.adapters.base import FPSBenchModel
from fpsbench.media import Media


class MyModel(FPSBenchModel):
    name = "my-model"

    def __init__(self, seed: int = 42):
        # Load your model / client here. ``seed`` is passed by the harness.
        self.seed = seed

    def predict(self, example: Dict[str, Any], media: Media) -> Dict[str, Any]:
        prompt = example["prompt"]  # question + choices, NO answer leakage

        # Decide how to consume media based on what the harness prepared:
        #   media.local_video_path  -> a prepared local clip (video mode)
        #   media.sampled_frames     -> list of frame paths (frames mode)
        #   media.source_url         -> original URL (source-url mode)
        #   all None                 -> text-only mode

        # ---- replace this stub with a real model call ----
        raw_response = "A. (template adapter: replace MyModel.predict with a real call)"
        return {
            "prediction": None,  # let the harness parse from raw_response
            "raw_response": raw_response,
            "metadata": {"adapter": self.name},
        }
