from __future__ import annotations

from meantbyme.adapters.storage import SQLiteRepository
from meantbyme.core.domain import (
    ASRResult,
    QAResponse,
    RiskLevel,
    UncertaintyBand,
)
from meantbyme.core.qa import QARuntime


class FixedASR:
    def transcribe(self, audio_id: str) -> list[ASRResult]:
        del audio_id
        return [
            ASRResult(
                provider="primary",
                transcript="why sky blue",
                language="en",
                status="success",
            ),
            ASRResult(
                provider="secondary",
                transcript="why is the sky blue",
                language="en",
                status="success",
            ),
        ]


class FixedQA:
    def __init__(
        self, *, uncertainty: UncertaintyBand = UncertaintyBand.MEDIUM
    ) -> None:
        self.uncertainty = uncertainty
        self.history_sizes: list[int] = []

    def respond(
        self, evidence, history, memories, *, language, situation
    ) -> QAResponse:
        del evidence, memories, language, situation
        self.history_sizes.append(len(history))
        return QAResponse(
            understood_question="Why is the sky blue?",
            patient_supported_spans=["sky", "blue"],
            ai_added_spans=["Why is the"],
            uncertainty=self.uncertainty,
            should_clarify=False,
            answer="Because air scatters blue light strongly.",
            risk_level=RiskLevel.ORDINARY,
        )


def _runtime(qa: FixedQA) -> tuple[QARuntime, SQLiteRepository]:
    repository = SQLiteRepository()
    repository.add_patient("patient-qa", "QA Patient")
    runtime = QARuntime(
        session_id="qa-session",
        patient_id="patient-qa",
        language="en",
        asr=FixedASR(),
        qa=qa,
        repository=repository,
    )
    return runtime, repository


def test_qa_direct_answer_is_temporary_and_has_no_expression_receipt() -> None:
    qa = FixedQA()
    runtime, repository = _runtime(qa)

    response = runtime.ask(audio_id="audio-1", turn_id="turn-1")

    assert response.should_clarify is False
    assert len(runtime.history) == 2
    assert repository.get_receipt("patient-qa", "qa-session") is None
    assert repository.search_verified_memories(
        "patient-qa", ["blue"]
    ) == []
    assert qa.history_sizes == [0]
    repository.close()


def test_cancelled_qa_turn_is_removed_from_followup_context() -> None:
    qa = FixedQA()
    runtime, repository = _runtime(qa)
    runtime.ask(audio_id="audio-1", turn_id="turn-1")

    assert runtime.cancel_turn("turn-1") is True
    runtime.ask(audio_id="audio-2", turn_id="turn-2")

    assert qa.history_sizes == [0, 0]
    assert {turn.turn_id for turn in runtime.history} == {"turn-2"}
    repository.close()


def test_high_uncertainty_answer_is_replaced_with_clarification() -> None:
    runtime, repository = _runtime(
        FixedQA(uncertainty=UncertaintyBand.HIGH)
    )

    response = runtime.ask(audio_id="audio-1", turn_id="turn-1")

    assert response.should_clarify is True
    assert response.answer is None
    assert response.clarification_question
    repository.close()
