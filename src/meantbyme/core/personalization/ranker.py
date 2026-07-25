from meantbyme.core.domain import (
    ExpressionCandidate,
    MemoryItem,
    VerificationLevel,
)
from meantbyme.core.personalization.text import normalize


def _score(
    candidate: ExpressionCandidate, memories: list[MemoryItem]
) -> tuple[float, list[str]]:
    score = len(candidate.patient_supported_spans) * 10
    reasons = list(candidate.ranking_reasons)
    normalized_candidate = normalize(candidate.text)

    for memory in memories:
        if memory.text is None:
            continue
        if memory.verification_level is VerificationLevel.UNVERIFIED:
            continue
        exact_weight = 1_000
        support_weight = 100
        similarity_weight = 25
        level_reason = "trusted"
        confidence = 1.0
        if memory.context.get("kind") == "expression_mapping":
            confidence = float(memory.context.get("confidence", 0.0))
            level_reason = f"learned ({confidence:.0%} confidence)"

        if normalize(memory.text) == normalized_candidate:
            score += exact_weight * confidence
            reasons.append(f"exact {level_reason} phrase")
        if memory.id in candidate.memory_support_ids:
            score += support_weight * confidence
            reasons.append(f"{level_reason} memory support")
        if memory.similarity_band == "high":
            score += similarity_weight * confidence
            reasons.append(f"high-similarity {level_reason} memory")

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
        memory.verification_level is not VerificationLevel.UNVERIFIED
        and memory.similarity_band == "high"
        and (
            memory.context.get("kind") != "expression_mapping"
            or float(memory.context.get("confidence", 0.0)) >= 0.55
        )
        for memory in memories
    )
