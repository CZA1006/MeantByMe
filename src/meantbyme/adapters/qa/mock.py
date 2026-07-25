from __future__ import annotations

from meantbyme.core.domain import (
    MemoryItem,
    QAConversationTurn,
    QAResponse,
    RiskLevel,
    TranscriptEvidence,
    UncertaintyBand,
)


class MockQAAdapter:
    """Deterministic QA fixture for local development and safety tests."""

    def respond(
        self,
        evidence: TranscriptEvidence,
        history: list[QAConversationTurn],
        memories: list[MemoryItem],
        *,
        language: str | None,
        situation: str | None,
    ) -> QAResponse:
        del history, memories, situation
        question = _best_transcript(evidence)
        supported = [question] if question else []
        if len(question.strip()) < 3:
            prompt = (
                "我还没有听清你的问题，可以再多说一点吗？"
                if (language or "").startswith("zh")
                else "I did not catch the question. Could you say a little more?"
            )
            return QAResponse(
                understood_question=question or "未听清的问题",
                patient_supported_spans=supported,
                ai_added_spans=[],
                uncertainty=UncertaintyBand.HIGH,
                should_clarify=True,
                clarification_question=prompt,
                answer=None,
                risk_level=RiskLevel.ORDINARY,
            )

        if (language or "").startswith("zh"):
            answer = (
                f"我理解你在问“{question}”。这是模拟模式下的回答，"
                "接入云模型后会根据问题和前文给出实际回答。"
            )
        else:
            answer = (
                f'I understand your question as "{question}". '
                "This is a deterministic mock answer."
            )
        return QAResponse(
            understood_question=question,
            patient_supported_spans=supported,
            ai_added_spans=[],
            uncertainty=UncertaintyBand.MEDIUM,
            should_clarify=False,
            clarification_question=None,
            answer=answer,
            risk_level=RiskLevel.ORDINARY,
        )


def _best_transcript(evidence: TranscriptEvidence) -> str:
    for result in evidence.results:
        if result.status == "success" and result.transcript.strip():
            return result.transcript.strip()
    return ""
