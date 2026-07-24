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

CJK_HIGH_RISK_LEXICON = frozenset(
    {
        "医生",
        "医院",
        "治疗",
        "检查",
        "药物",
        "用药",
        "吃药",
        "服药",
        "停药",
        "剂量",
        "处方",
        "手术",
        "急救",
        "救护车",
        "紧急",
        "报警",
        "自杀",
        "银行",
        "转账",
        "付款",
        "支付",
        "合同",
        "签字",
        "签署",
        "法律",
        "律师",
        "遗嘱",
        "分手",
        "离婚",
        "结婚",
    }
)

NUMERIC_HIGH_RISK_CODES = frozenset({"110", "120"})

_SEVERITY = {
    RiskLevel.ORDINARY: 0,
    RiskLevel.SENSITIVE: 1,
    RiskLevel.HIGH_RISK: 2,
}


def _matches_high_risk(text: str) -> bool:
    lowered = text.casefold()
    latin_match = any(
        re.search(rf"\b{re.escape(term)}\b", lowered)
        for term in HIGH_RISK_LEXICON
    )
    cjk_match = any(
        term in lowered for term in CJK_HIGH_RISK_LEXICON
    )
    numeric_match = any(
        re.search(rf"(?<!\d){code}(?!\d)", lowered)
        for code in NUMERIC_HIGH_RISK_CODES
    )
    return latin_match or cjk_match or numeric_match


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
