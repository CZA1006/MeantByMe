from __future__ import annotations

import hashlib
import math

from meantbyme.core.personalization.text import tokenize


EMBEDDING_DIMENSIONS = 64
MIN_RETRIEVAL_CONFIDENCE = 0.55


def embed_expression(text: str) -> list[float]:
    """Create a small deterministic embedding without a model dependency."""

    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    return max(
        0.0,
        min(1.0, sum(a * b for a, b in zip(left, right, strict=True))),
    )


def update_mapping_confidence(
    current: float | None,
    *,
    confirmed: bool,
) -> float:
    """Bounded, explainable feedback update used by the deterministic shell."""

    if current is None:
        return 0.65 if confirmed else 0.35
    delta = 0.10 if confirmed else -0.20
    return round(max(0.05, min(0.98, current + delta)), 4)

