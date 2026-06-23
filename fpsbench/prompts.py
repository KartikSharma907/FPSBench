"""Prompt construction for model evaluation.

The prompting protocol deliberately exposes only the question text, the answer
choices, and (optionally) media. It never leaks the correct answer, answer_text,
min_fps, or the temporal certificate, unless a diagnostic flag explicitly asks
for them.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from . import ANSWER_CHOICES

__all__ = ["DEFAULT_SYSTEM_PROMPT", "build_prompt", "ordered_choices"]

DEFAULT_SYSTEM_PROMPT = (
    "Analyze the video carefully, focusing on rapid motion and fine-grained "
    "temporal details. Answer the multiple-choice question. Start your response "
    "with exactly one option letter from the available choices, then provide a "
    "brief explanation."
)


def ordered_choices(
    choices: Dict[str, str],
    *,
    include_none_of_above: bool = True,
    shuffle: bool = False,
    seed: Optional[int] = None,
) -> List[Tuple[str, str]]:
    """Return choices as an ordered list of ``(letter, text)`` pairs.

    Args:
        choices: mapping like ``{"A": "...", "B": "...", ...}``.
        include_none_of_above: if False, the "None of the above" choice (E) is
            dropped from the presented options.
        shuffle: if True, the *texts* are shuffled across letters (re-lettered
            A, B, C, ...). "None of the above" is always kept last regardless of
            shuffling, matching how human annotators saw it.
        seed: RNG seed for reproducible shuffling.
    """
    items = [(k, v) for k, v in choices.items() if v is not None]
    items.sort(key=lambda kv: ANSWER_CHOICES.index(kv[0]))

    none_items = [kv for kv in items if kv[1] == "None of the above"]
    real_items = [kv for kv in items if kv[1] != "None of the above"]

    if not include_none_of_above:
        none_items = []

    texts = [text for _, text in real_items]
    if shuffle:
        rng = random.Random(seed)
        rng.shuffle(texts)

    texts += [text for _, text in none_items]
    letters = list(ANSWER_CHOICES)[: len(texts)]
    return list(zip(letters, texts))


def build_prompt(
    example: Dict,
    *,
    include_none_of_above: bool = True,
    shuffle: bool = False,
    seed: Optional[int] = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> Tuple[str, List[Tuple[str, str]], Dict[str, str]]:
    """Build the user prompt for an example.

    Returns ``(prompt_text, presented_choices, letter_to_text)`` where
    ``presented_choices`` is the ordered ``(letter, text)`` list actually shown
    and ``letter_to_text`` maps the presented letters to their texts (useful for
    re-mapping a shuffled prediction back to the canonical answer).
    """
    q = example["question"]
    presented = ordered_choices(
        q["choices"],
        include_none_of_above=include_none_of_above,
        shuffle=shuffle,
        seed=seed,
    )
    letters = ", ".join(letter for letter, _ in presented)
    options_block = "\n".join(f"{letter}. {text}" for letter, text in presented)

    prompt = (
        f"{system_prompt}\n\n"
        f"Question: {q['text']}\n\n"
        f"Options:\n{options_block}\n\n"
        f"Respond with exactly one of these option letters ({letters}), "
        f"then a brief explanation."
    )
    return prompt, presented, {letter: text for letter, text in presented}
