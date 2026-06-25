"""Base adapter interface for plugging a model into FPS-Bench evaluation."""

from __future__ import annotations

from typing import Any, Dict

from ..media import Media

__all__ = ["FPSBenchModel", "EchoAdapter"]


class FPSBenchModel:
    """Interface every model adapter implements.

    Subclasses override :meth:`predict`. The evaluation harness builds the
    prompt and media bundle and never passes the correct answer to the adapter
    (unless an explicit debugging flag is used upstream).
    """

    #: Optional human-readable name surfaced in result metadata.
    name: str = "fpsbench-model"

    def predict(self, example: Dict[str, Any], media: Media) -> Dict[str, Any]:
        """Return a prediction for one example.

        Args:
            example: a dict with at least ``id`` and ``prompt`` (the fully built
                prompt string) plus ``presented_choices`` (list of ``(letter,
                text)``). It does not contain the correct answer.
            media: a :class:`fpsbench.media.Media` bundle. Inspect its fields to
                decide how to consume the input (local video, frames, source URL,
                or text-only when all are ``None``).

        Returns:
            ``{"prediction": "A", "raw_response": "...", "metadata": {...}}``.
            ``prediction`` should be one of A/B/C/D/E or ``None`` if the model
            declined / produced no parseable answer.
        """
        raise NotImplementedError


class EchoAdapter(FPSBenchModel):
    """Debug adapter that echoes a fixed or first available letter.

    Useful for smoke-testing the pipeline without any model dependency. Always
    predicts the first presented option letter.
    """

    name = "echo-debug"

    def predict(self, example: Dict[str, Any], media: Media) -> Dict[str, Any]:
        presented = example.get("presented_choices") or [("A", "")]
        letter = presented[0][0]
        return {
            "prediction": letter,
            "raw_response": f"{letter} (echo debug adapter)",
            "metadata": {"adapter": self.name},
        }
