from meantbyme.core.domain import (
    ExpressionCandidate,
    MemoryItem,
    VerificationLevel,
)
from meantbyme.core.personalization.text import normalize


def _score(
    candidate: ExpressionCandidate, memories: list[MemoryItem]
) -> tuple[int, list[str]]:
    score = len(candidate.patient_supported_spans) * 10
    reasons = list(candidate.ranking_reasons)
    normalized_candidate = normalize(candidate.text)

    for memory in memories:
        if memory.text is None:
            continue
        if normalize(memory.text) == normalized_candidate:
            score += 1_000
            reasons.append("exact verified patient phrase")
        elif memory.id in candidate.memory_support_ids:
            score += 100
            reasons.append("verified memory support")
        if memory.similarity_band == "high":
            score += 25

    score -= len(candidate.ai_added_spans) * 2
    return score, list(dict.fromkeys(reasons))


def rank_candidates(
    candidates: list[ExpressionCandidate], memories: list[MemoryItem]
) -> list[ExpressionCandidate]:
    scored = []
    for index, candidate in enumerate(candidates):
        score, reasons = _score(candidate, memories)
        scored.append(
            (
                -score,
                index,
                candidate.model_copy(update={"ranking_reasons": reasons}),
            )
        )
    return [item[2] for item in sorted(scored)]


def has_strong_verified_match(memories: list[MemoryItem]) -> bool:
    return any(
        memory.verification_level is VerificationLevel.GOLD
        and memory.similarity_band == "high"
        for memory in memories
    )
