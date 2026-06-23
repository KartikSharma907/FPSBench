"""Model adapters for FPS-Bench.

Lightweight adapters (base, echo, random) are re-exported here. Adapters with
heavy/optional dependencies (OpenAI, Gemini, HuggingFace) are imported lazily by
the evaluation harness via ``module:Class`` strings, so importing this package
never pulls in those dependencies.
"""

from .base import EchoAdapter, FPSBenchModel
from .random_baseline import RandomBaselineAdapter

__all__ = ["FPSBenchModel", "EchoAdapter", "RandomBaselineAdapter"]
