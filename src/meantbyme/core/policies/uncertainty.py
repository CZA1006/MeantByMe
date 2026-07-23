from meantbyme.core.domain import TranscriptEvidence, UncertaintyBand
from meantbyme.core.personalization.text import tokenize


PREDICATES = frozenset(
    {
        "am",
        "are",
        "call",
        "cancel",
        "decide",
        "feel",
        "give",
        "go",
        "help",
        "is",
        "leave",
        "meet",
        "move",
        "need",
        "pay",
        "sign",
        "stop",
        "take",
        "transfer",
        "want",
    }
)
TIME_WORDS = frozenset(
    {
        "today",
        "tomorrow",
        "tonight",
        "morning",
        "afternoon",
        "evening",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    }
)
FUNCTION_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "do",
        "don't",
        "i",
        "my",
        "not",
        "please",
        "the",
        "to",
        "we",
        "you",
    }
)
CORE_MISSING_SLOTS = frozenset(
    {
        "action",
        "action_or_object",
        "core",
        "object",
        "predicate",
        "predicate_or_object",
        "time",
    }
)


def core_slots_present(stable_fragments: list[str]) -> bool:
    tokens = set(tokenize(" ".join(stable_fragments)))
    has_predicate = bool(tokens & PREDICATES)
    has_time = bool(tokens & TIME_WORDS)
    possible_objects = tokens - PREDICATES - TIME_WORDS - FUNCTION_WORDS
    return has_predicate and (has_time or bool(possible_objects))


def assess_uncertainty(evidence: TranscriptEvidence) -> UncertaintyBand:
    failed_count = sum(result.status != "success" for result in evidence.results)
    both_asr_failed = len(evidence.results) >= 2 and failed_count == len(
        evidence.results
    )
    missing_core = bool(set(evidence.missing_slots) & CORE_MISSING_SLOTS)
    core_present = core_slots_present(evidence.stable_fragments)

    if (
        both_asr_failed
        or len(evidence.stable_fragments) < 2
        or (missing_core and bool(evidence.conflicts))
    ):
        return UncertaintyBand.HIGH
    if (
        not evidence.conflicts
        and not evidence.missing_slots
        and core_present
    ):
        return UncertaintyBand.LOW
    return UncertaintyBand.MEDIUM
