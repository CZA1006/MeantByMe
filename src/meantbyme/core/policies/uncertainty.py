import re

from meantbyme.core.domain import TranscriptEvidence, UncertaintyBand
from meantbyme.core.personalization.text import normalize, tokenize


ENGLISH_PREDICATES = frozenset(
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
ENGLISH_TIME_WORDS = frozenset(
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
ENGLISH_FUNCTION_WORDS = frozenset(
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
CJK_PREDICATES = frozenset(
    {
        "想",
        "要",
        "去",
        "来",
        "做",
        "吃",
        "喝",
        "停",
        "换",
        "见",
        "打",
        "付",
        "签",
        "需要",
        "帮",
        "走",
        "回",
    }
)
CJK_TIME_WORDS = frozenset(
    {
        "今天",
        "明天",
        "后天",
        "昨天",
        "早上",
        "中午",
        "下午",
        "晚上",
        *(f"周{day}" for day in "一二三四五六日"),
        *(f"星期{day}" for day in "一二三四五六日"),
    }
)
CJK_FUNCTION_WORDS = frozenset(
    {
        "我",
        "你",
        "他",
        "她",
        "它",
        "们",
        "的",
        "了",
        "吗",
        "呢",
        "吧",
        "请",
        "不",
        "没",
        "很",
        "也",
        "都",
        "再",
    }
)

# Evidence extraction imports this set to detect whether a predicate is stable.
# Single-character CJK entries align with the tokenizer's CJK granularity.
PREDICATES = ENGLISH_PREDICATES | {
    predicate for predicate in CJK_PREDICATES if len(predicate) == 1
}
TIME_WORDS = ENGLISH_TIME_WORDS
FUNCTION_WORDS = ENGLISH_FUNCTION_WORDS
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
_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def core_slots_present(stable_fragments: list[str]) -> bool:
    normalized = normalize(" ".join(stable_fragments))
    if _CJK_PATTERN.search(normalized):
        compact = normalized.replace(" ", "")
        has_predicate = any(
            predicate in compact for predicate in CJK_PREDICATES
        )
        has_time = any(time_word in compact for time_word in CJK_TIME_WORDS)
        remaining = compact
        removable = CJK_PREDICATES | CJK_TIME_WORDS | CJK_FUNCTION_WORDS
        for word in sorted(removable, key=len, reverse=True):
            remaining = remaining.replace(word, "")
        return has_predicate and (has_time or bool(tokenize(remaining)))

    tokens = set(tokenize(normalized))
    has_predicate = bool(tokens & ENGLISH_PREDICATES)
    has_time = bool(tokens & ENGLISH_TIME_WORDS)
    possible_objects = (
        tokens
        - ENGLISH_PREDICATES
        - ENGLISH_TIME_WORDS
        - ENGLISH_FUNCTION_WORDS
    )
    return has_predicate and (has_time or bool(possible_objects))


def assess_uncertainty(evidence: TranscriptEvidence) -> UncertaintyBand:
    successful_count = sum(
        result.status == "success" for result in evidence.results
    )
    failed_count = len(evidence.results) - successful_count
    both_asr_failed = len(evidence.results) >= 2 and failed_count == len(
        evidence.results
    )
    missing_core = bool(set(evidence.missing_slots) & CORE_MISSING_SLOTS)
    core_present = core_slots_present(evidence.stable_fragments)
    single_source_reviewable = (
        successful_count == 1
        and len(evidence.uncertain_fragments) >= 6
        and core_slots_present(evidence.uncertain_fragments)
    )

    if both_asr_failed:
        return UncertaintyBand.HIGH
    if single_source_reviewable:
        return UncertaintyBand.MEDIUM
    if len(evidence.stable_fragments) < 2 or (
        missing_core and bool(evidence.conflicts)
    ):
        return UncertaintyBand.HIGH
    if (
        not evidence.conflicts
        and not evidence.missing_slots
        and core_present
    ):
        return UncertaintyBand.LOW
    return UncertaintyBand.MEDIUM
