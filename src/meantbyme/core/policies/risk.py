import re

from meantbyme.core.domain import RiskLevel


HIGH_RISK_LEXICON = frozenset(
    {
        "911",
        "ambulance",
        "bank",
        "break up",
        "contract",
        "divorce",
        "doctor",
        "dose",
        "emergency",
        "hospital",
        "lawyer",
        "legal",
        "marry",
        "medication",
        "money",
        "overdose",
        "prescription",
        "sign",
        "suicide",
        "transfer",
        "treatment",
        "will",
    }
)

_SEVERITY = {
    RiskLevel.ORDINARY: 0,
    RiskLevel.SENSITIVE: 1,
    RiskLevel.HIGH_RISK: 2,
}


def _matches_high_risk(text: str) -> bool:
    lowered = text.casefold()
    return any(
        re.search(rf"\b{re.escape(term)}\b", lowered)
        for term in HIGH_RISK_LEXICON
    )


def classify_risk(
    text: str, llm_hint: RiskLevel | str | None = None
) -> RiskLevel:
    rule_level = (
        RiskLevel.HIGH_RISK
        if _matches_high_risk(text)
        else RiskLevel.ORDINARY
    )
    hinted_level = RiskLevel(llm_hint) if llm_hint else RiskLevel.ORDINARY
    return max((rule_level, hinted_level), key=_SEVERITY.__getitem__)
