from meantbyme.core.domain import (
    ASRResult,
    RiskLevel,
    TranscriptEvidence,
    UncertaintyBand,
)
from meantbyme.core.policies import assess_uncertainty, classify_risk


def _result(status: str, transcript: str = "") -> ASRResult:
    return ASRResult(
        provider=f"mock-{status}",
        transcript=transcript,
        status=status,
    )


def test_uncertainty_is_high_when_both_asr_fail() -> None:
    evidence = TranscriptEvidence(
        results=[_result("failed"), _result("timeout")],
        stable_fragments=[],
        uncertain_fragments=[],
        conflicts=[],
        missing_slots=["predicate"],
        evidence_band=UncertaintyBand.HIGH,
    )
    assert assess_uncertainty(evidence) is UncertaintyBand.HIGH


def test_uncertainty_is_low_only_with_complete_core_slots() -> None:
    evidence = TranscriptEvidence(
        results=[
            _result("success", "I want water"),
            _result("success", "I want water"),
        ],
        stable_fragments=["i", "want", "water"],
        uncertain_fragments=[],
        conflicts=[],
        missing_slots=[],
        evidence_band=UncertaintyBand.LOW,
    )
    assert assess_uncertainty(evidence) is UncertaintyBand.LOW


def test_llm_hint_can_raise_but_never_lower_rule_risk() -> None:
    assert (
        classify_risk("Transfer money now", RiskLevel.ORDINARY)
        is RiskLevel.HIGH_RISK
    )
    assert (
        classify_risk("Please open the window", RiskLevel.HIGH_RISK)
        is RiskLevel.HIGH_RISK
    )
