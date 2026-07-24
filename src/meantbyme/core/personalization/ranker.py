import re

from meantbyme.core.domain import (
    ExpressionCandidate,
    MemoryItem,
    MemoryType,
    VerificationLevel,
)
from meantbyme.core.personalization.text import normalize, tokenize


# Function/stop words that must not, on their own, count as "grounded in
# context" — reusing a pronoun or article is not evidence of personalization.
_GROUNDING_STOPWORDS = frozenset(
    {
        "i", "we", "you", "they", "he", "she", "it", "the", "a", "an",
        "to", "and", "or", "of", "in", "on", "at", "is", "are", "am", "be",
        "my", "our", "your", "their", "not", "do", "please", "this", "that",
        "we're", "don't", "after", "only", "with", "for", "me",
        "help", "need", "needs", "want", "wants",
    }
)
_CJK_TOKEN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_GOLD_CONTEXT_MAX = 20
_SILVER_CONTEXT_MAX = 5


def _content_tokens(text: str) -> set[str]:
    return {
        token
        for token in tokenize(text)
        if (
            (len(token) > 1 or _CJK_TOKEN.search(token))
            and token not in _GROUNDING_STOPWORDS
        )
    }


def _context_token_sets(
    context_memories: list[MemoryItem] | None,
) -> tuple[set[str], set[str]]:
    gold: set[str] = set()
    silver: set[str] = set()
    for memory in context_memories or []:
        if (
            not memory.text
            or memory.memory_type is not MemoryType.CONTEXT
            or memory.verification_level
            not in {VerificationLevel.GOLD, VerificationLevel.SILVER}
        ):
            continue
        target = (
            gold
            if memory.verification_level is VerificationLevel.GOLD
            else silver
        )
        target |= _content_tokens(memory.text)
    return gold, silver


def _score(
    candidate: ExpressionCandidate,
    memories: list[MemoryItem],
    gold_context: set[str],
    silver_context: set[str],
) -> tuple[int, list[str]]:
    score = len(candidate.patient_supported_spans) * 10
    reasons = list(candidate.ranking_reasons)
    normalized_candidate = normalize(candidate.text)

    for memory in memories:
        if memory.text is None:
            continue
        is_gold = memory.verification_level is VerificationLevel.GOLD
        exact_weight = 1_000 if is_gold else 250
        support_weight = 100 if is_gold else 40
        similarity_weight = 25 if is_gold else 8
        level_reason = "gold patient" if is_gold else "silver-assisted"

        if normalize(memory.text) == normalized_candidate:
            score += exact_weight
            reasons.append(f"exact {level_reason} phrase")
        if memory.id in candidate.memory_support_ids:
            score += support_weight
            reasons.append(f"{level_reason} memory support")
        if memory.similarity_band == "high":
            score += similarity_weight
            reasons.append(f"high-similarity {level_reason} memory")

    score -= len(candidate.ai_added_spans) * 2

    # D21: a modest boost when AI-added content is grounded in the patient's
    # verified CONTEXT memory, so a memory-informed completion is not buried by
    # its own ai_added penalty. Far below a Gold *semantic* exact/support match
    # (patient-confirmed phrasing), and never enough to auto-select — the
    # patient still explicitly selects and confirms. Context is evidence for
    # ranking only, never patient-confirmed intent.
    added_tokens: set[str] = set()
    for span in candidate.ai_added_spans:
        added_tokens |= _content_tokens(span)
    gold_overlap = added_tokens & gold_context
    silver_overlap = added_tokens & silver_context
    if added_tokens and gold_overlap:
        context_score = max(
            1,
            round(
                _GOLD_CONTEXT_MAX
                * len(gold_overlap)
                / len(added_tokens)
            ),
        )
        score += context_score
        reasons.append(
            "grounded in gold patient context "
            f"({len(gold_overlap)}/{len(added_tokens)} content tokens)"
        )
    elif added_tokens and silver_overlap:
        context_score = max(
            1,
            round(
                _SILVER_CONTEXT_MAX
                * len(silver_overlap)
                / len(added_tokens)
            ),
        )
        score += context_score
        reasons.append(
            "grounded in silver caregiver context "
            f"({len(silver_overlap)}/{len(added_tokens)} content tokens)"
        )

    return score, list(dict.fromkeys(reasons))


def rank_candidates(
    candidates: list[ExpressionCandidate],
    memories: list[MemoryItem],
    context_memories: list[MemoryItem] | None = None,
) -> list[ExpressionCandidate]:
    gold_context, silver_context = _context_token_sets(context_memories)
    scored = []
    for index, candidate in enumerate(candidates):
        score, reasons = _score(
            candidate, memories, gold_context, silver_context
        )
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
