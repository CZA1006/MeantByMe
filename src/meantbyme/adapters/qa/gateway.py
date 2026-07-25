from __future__ import annotations

import logging

from pydantic import ValidationError

from meantbyme.adapters.http import (
    GatewayError,
    GatewayHTTPError,
    GatewayInvalidResponse,
    GatewayTimeout,
)
from meantbyme.core.domain import (
    MemoryItem,
    QAConversationTurn,
    QAResponse,
    QAStatus,
    RiskLevel,
    TranscriptEvidence,
    UncertaintyBand,
)


logger = logging.getLogger("meantbyme.qa.gateway")


class GatewayQAAdapter:
    def __init__(
        self,
        *,
        client,
        patient_id: str,
        session_id: str,
    ) -> None:
        self._client = client
        self._patient_id = patient_id
        self._session_id = session_id

    def respond(
        self,
        evidence: TranscriptEvidence,
        history: list[QAConversationTurn],
        memories: list[MemoryItem],
        *,
        language: str | None,
        situation: str | None,
    ) -> QAResponse:
        payload = {
            "patient_id": self._patient_id,
            "session_id": self._session_id,
            "language": language,
            "situation": situation,
            "evidence": evidence.model_dump(mode="json"),
            "history": [
                turn.model_dump(mode="json") for turn in history[-12:]
            ],
            "memories": [
                {
                    "id": memory.id,
                    "memory_type": memory.memory_type.value,
                    "verification_level": memory.verification_level.value,
                    "text": memory.text,
                    "language": memory.language,
                    "context": memory.context,
                    "similarity_band": memory.similarity_band,
                }
                for memory in memories[:12]
            ],
        }
        try:
            response = self._client.post_json("/v1/qa/respond", payload)
            return QAResponse.model_validate(response.get("response", response))
        except GatewayTimeout:
            reason = "gateway_timeout"
        except GatewayHTTPError as error:
            reason = f"gateway_http_{error.status_code}"
        except GatewayInvalidResponse:
            reason = "gateway_invalid_response"
        except GatewayError:
            reason = "gateway_unavailable"
        except (ValidationError, TypeError, ValueError):
            reason = "qa_response_contract_failed"
        logger.warning("qa_fallback reason=%s", reason)
        return _safe_fallback(evidence, language=language, reason=reason)


def _safe_fallback(
    evidence: TranscriptEvidence,
    *,
    language: str | None,
    reason: str,
) -> QAResponse:
    question = next(
        (
            result.transcript.strip()
            for result in evidence.results
            if result.status == "success" and result.transcript.strip()
        ),
        "未识别的问题" if (language or "").startswith("zh") else "unheard question",
    )
    clarification = (
        "我现在暂时无法回答，可以稍后再问一次吗？"
        if (language or "").startswith("zh")
        else "I cannot answer right now. Could you try again shortly?"
    )
    return QAResponse(
        understood_question=question,
        patient_supported_spans=[question],
        ai_added_spans=[],
        uncertainty=UncertaintyBand.HIGH,
        should_clarify=True,
        clarification_question=clarification,
        answer=None,
        risk_level=RiskLevel.ORDINARY,
        status=QAStatus.FALLBACK,
        error=reason,
    )
