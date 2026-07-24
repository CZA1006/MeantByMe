from services.gateway.prompts import INTENT_SYSTEM_PROMPT


PROMPT = " ".join(INTENT_SYSTEM_PROMPT.split())


def test_intent_prompt_keeps_evidence_and_authority_distinct() -> None:
    assert "locked patient-confirmed content" in PROMPT
    assert "uncertain ASR" in PROMPT
    assert "remains evidence, not authority" in PROMPT
    assert "A shorter completion is not automatically better" in PROMPT
    assert "memory_support_ids may reference ONLY semantic memories" in (
        PROMPT
    )


def test_intent_prompt_never_exposes_operational_authority() -> None:
    assert "never decide the patient's intent" in PROMPT
    assert "Never include speak" in PROMPT
    assert "write_memory" in PROMPT
