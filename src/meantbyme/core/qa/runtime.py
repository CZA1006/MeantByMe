from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from meantbyme.core.domain import (
    QAConversationTurn,
    QAEvent,
    QAEventType,
    QARole,
    QAResponse,
    RiskLevel,
    UncertaintyBand,
)
from meantbyme.core.personalization import compose_situation
from meantbyme.core.policies import classify_risk
from meantbyme.core.ports import ASRPort, QAPort, RepositoryPort
from meantbyme.core.runtime.evidence import build_transcript_evidence


class QARuntimeError(RuntimeError):
    pass


class QARuntime:
    """A temporary, neutral-voice AI conversation.

    The runtime deliberately has no TTS authorization or memory-write methods.
    Its history is process-local and disappears when the QA session is closed.
    """

    def __init__(
        self,
        *,
        session_id: str,
        patient_id: str,
        language: str,
        asr: ASRPort,
        qa: QAPort,
        repository: RepositoryPort,
        situation: str | None = None,
        max_history_turns: int = 12,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.session_id = session_id
        self.patient_id = patient_id
        self.language = language
        self._asr = asr
        self._qa = qa
        self._repository = repository
        self._situation_override = situation
        self._max_history_turns = max(2, max_history_turns)
        self._now = clock
        self._history: list[QAConversationTurn] = []
        self._events: list[QAEvent] = []
        self._stopped = False
        self._emit(QAEventType.SESSION_STARTED, {"language": language})

    @property
    def history(self) -> tuple[QAConversationTurn, ...]:
        return tuple(turn.model_copy(deep=True) for turn in self._history)

    @property
    def events(self) -> tuple[QAEvent, ...]:
        return tuple(event.model_copy(deep=True) for event in self._events)

    @property
    def stopped(self) -> bool:
        return self._stopped

    def ask(self, *, audio_id: str, turn_id: str) -> QAResponse:
        if self._stopped:
            raise QARuntimeError("QA session is stopped")
        if any(turn.turn_id == turn_id for turn in self._history):
            raise QARuntimeError("QA turn already exists")

        results = self._asr.transcribe(audio_id)
        evidence = build_transcript_evidence(results)
        transcript = next(
            (
                item.transcript.strip()
                for item in results
                if item.status == "success" and item.transcript.strip()
            ),
            "",
        )
        if not transcript:
            raise QARuntimeError("No usable speech transcript")
        self._emit(
            QAEventType.EVIDENCE_EXTRACTED,
            {
                "turn_id": turn_id,
                "evidence_band": evidence.evidence_band.value,
                "successful_asr_count": sum(
                    item.status == "success" for item in results
                ),
            },
        )

        fragments = [
            *evidence.stable_fragments,
            *evidence.uncertain_fragments,
        ] or [transcript]
        memories = self._repository.search_verified_memories(
            self.patient_id, fragments
        )
        contexts = self._repository.search_context_memories(
            self.patient_id,
            fragments=None,
            limit=8,
        )
        situation = compose_situation(
            contexts,
            now=self._now(),
            override=self._situation_override,
        )
        response = self._qa.respond(
            evidence,
            list(self._history),
            memories,
            language=self.language,
            situation=situation,
        )
        response = self._enforce_response_policy(response)

        user_turn = QAConversationTurn(
            turn_id=turn_id,
            role=QARole.USER,
            content=response.understood_question,
            source="ai_interpreted_patient_question",
            patient_supported_spans=response.patient_supported_spans,
            ai_added_spans=response.ai_added_spans,
        )
        assistant_turn = QAConversationTurn(
            turn_id=turn_id,
            role=QARole.ASSISTANT,
            content=response.spoken_text(),
            source="ai_response",
        )
        self._history.extend((user_turn, assistant_turn))
        self._history = self._history[-self._max_history_turns :]
        self._emit(
            QAEventType.QUESTION_INTERPRETED,
            {
                "turn_id": turn_id,
                "uncertainty": response.uncertainty.value,
                "patient_supported_span_count": len(
                    response.patient_supported_spans
                ),
                "ai_added_span_count": len(response.ai_added_spans),
            },
        )
        self._emit(
            (
                QAEventType.CLARIFICATION_REQUESTED
                if response.should_clarify
                else QAEventType.ANSWER_GENERATED
            ),
            {
                "turn_id": turn_id,
                "risk_level": response.risk_level.value,
                "status": response.status.value,
            },
        )
        return response.model_copy(deep=True)

    def cancel_turn(self, turn_id: str) -> bool:
        before = len(self._history)
        self._history = [
            turn for turn in self._history if turn.turn_id != turn_id
        ]
        removed = len(self._history) != before
        self._emit(
            QAEventType.TURN_CANCELLED,
            {"turn_id": turn_id, "removed_from_history": removed},
        )
        return removed

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._emit(
            QAEventType.SESSION_STOPPED,
            {"history_turn_count": len(self._history)},
        )

    def _enforce_response_policy(self, response: QAResponse) -> QAResponse:
        risk = classify_risk(
            f"{response.understood_question} {response.spoken_text()}",
            response.risk_level,
        )
        if (
            response.uncertainty is UncertaintyBand.HIGH
            and not response.should_clarify
        ):
            clarification = (
                "我不确定是否正确理解了你的问题，可以换一种说法再问一次吗？"
                if self.language.startswith("zh")
                else (
                    "I am not sure I understood the question. "
                    "Could you ask it another way?"
                )
            )
            return response.model_copy(
                update={
                    "should_clarify": True,
                    "clarification_question": clarification,
                    "answer": None,
                    "risk_level": risk,
                }
            )
        return response.model_copy(update={"risk_level": risk})

    def _emit(self, event_type: QAEventType, payload: dict) -> None:
        self._events.append(
            QAEvent(
                event_id=str(uuid4()),
                event_type=event_type,
                session_id=self.session_id,
                patient_id=self.patient_id,
                timestamp=self._now(),
                payload=payload,
            )
        )
