from difflib import SequenceMatcher

from meantbyme.core.domain import ASRResult, TranscriptEvidence, UncertaintyBand
from meantbyme.core.personalization.text import tokenize
from meantbyme.core.policies.uncertainty import PREDICATES, assess_uncertainty


def build_transcript_evidence(
    results: list[ASRResult],
) -> TranscriptEvidence:
    successful = [result for result in results if result.status == "success"]
    stable: list[str] = []
    uncertain: list[str] = []
    conflicts: list[list[str]] = []

    if len(successful) >= 2:
        primary_tokens = tokenize(successful[0].transcript)
        secondary_tokens = tokenize(successful[1].transcript)
        matcher = SequenceMatcher(a=primary_tokens, b=secondary_tokens)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            left = primary_tokens[i1:i2]
            right = secondary_tokens[j1:j2]
            if tag == "equal":
                stable.extend(left)
            elif tag in {"insert", "delete"}:
                uncertain.extend(left or right)
            else:
                conflicts.append(left + right)
                uncertain.extend(left + right)
    elif len(successful) == 1:
        uncertain = tokenize(successful[0].transcript)

    stable_tokens = set(stable)
    missing_slots = []
    if not stable_tokens.intersection(PREDICATES):
        missing_slots.append("predicate")

    provisional = TranscriptEvidence(
        results=results,
        stable_fragments=stable,
        uncertain_fragments=list(dict.fromkeys(uncertain)),
        conflicts=conflicts,
        missing_slots=missing_slots,
        evidence_band=UncertaintyBand.MEDIUM,
    )
    return provisional.model_copy(
        update={"evidence_band": assess_uncertainty(provisional)}
    )
