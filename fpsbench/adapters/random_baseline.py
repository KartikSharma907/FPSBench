"""Random-guessing baseline adapter."""

from __future__ import annotations

import random
from typing import Any, Dict

from ..media import Media
from .base import FPSBenchModel

__all__ = ["RandomBaselineAdapter"]


class RandomBaselineAdapter(FPSBenchModel):
    """Uniformly samples one of the presented option letters.

    Establishes the random reference (~20% for 5-way choices). Seeded for
    reproducibility; the seed can be set via the constructor or left to the
    evaluation harness which passes ``--seed``.
    """

    name = "random-baseline"

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)

    def predict(self, example: Dict[str, Any], media: Media) -> Dict[str, Any]:
        presented = example.get("presented_choices") or [("A", "")]
        letter = self._rng.choice([l for l, _ in presented])
        return {
            "prediction": letter,
            "raw_response": f"{letter} (random baseline guess)",
            "metadata": {"adapter": self.name},
        }
