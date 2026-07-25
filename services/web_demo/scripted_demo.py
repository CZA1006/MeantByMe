from __future__ import annotations

from meantbyme.core.domain import (
    ASRResult,
    ConfirmedContext,
    ExpressionCandidate,
    IntentProposal,
    MemoryItem,
    RiskLevel,
    TranscriptEvidence,
)
from meantbyme.core.personalization.text import normalize, tokenize


LIN_YUE_SCRIPTED_TEXT = (
    "Hi, I’d like to book a therapy appointment with Dr. Wang this "
    "Wednesday afternoon at 2 PM. Could you call me back? Thanks."
)


class LinYueScriptedASRAdapter:
    """Deterministic, offline ASR evidence for the live demonstration."""

    def transcribe(self, audio_id: str) -> list[ASRResult]:
        del audio_id
        return [
            ASRResult(
                provider="lin_yue_demo_primary",
                transcript=LIN_YUE_SCRIPTED_TEXT,
                language="en",
                segments=[],
                latency_ms=1750,
                status="success",
            ),
            ASRResult(
                provider="lin_yue_demo_secondary",
                transcript=LIN_YUE_SCRIPTED_TEXT,
                language="en",
                segments=[],
                latency_ms=1750,
                status="success",
            ),
        ]


class LinYueScriptedIntentAdapter:
    """Returns a fixed first candidate while preserving normal confirmation."""

    _alternatives = (
        (
            "Hi, I’d like to arrange a therapy appointment with Dr. Wang "
            "this Wednesday afternoon. Could you call me back? Thanks."
        ),
        (
            "Hi, could you call me back about booking a therapy appointment "
            "with Dr. Wang for Wednesday afternoon? Thanks."
        ),
    )

    def propose(
        self,
        evidence: TranscriptEvidence,
        memories: list[MemoryItem],
        confirmed_context: ConfirmedContext,
        situation: str | None = None,
    ) -> IntentProposal:
        del memories, situation
        rejected = {
            normalize(text) for text in confirmed_context.rejected_texts
        }
        supported = evidence.stable_fragments
        texts = (LIN_YUE_SCRIPTED_TEXT, *self._alternatives)
        candidates: list[ExpressionCandidate] = []
        for index, text in enumerate(texts):
            if normalize(text) in rejected:
                continue
            exact_script = text == LIN_YUE_SCRIPTED_TEXT
            candidates.append(
                ExpressionCandidate(
                    id=f"lin-yue-scripted-{index + 1}",
                    text=text,
                    language="en",
                    patient_supported_spans=(
                        list(supported)
                        if exact_script
                        else [
                            token
                            for token in tokenize(text)
                            if token in set(supported)
                        ][:12]
                    ),
                    ai_added_spans=(
                        []
                        if exact_script
                        else ["arrangement wording"]
                    ),
                    memory_support_ids=[],
                    ranking_reasons=[
                        (
                            "exact scripted demonstration transcript"
                            if exact_script
                            else "scripted demonstration alternative"
                        )
                    ],
                    risk_level=RiskLevel.ORDINARY,
                    source_level="L1" if exact_script else "L2",
                )
            )

        if len(candidates) < 2:
            candidates = self._fallback_candidates(rejected)

        return IntentProposal(
            certain_content=list(supported),
            uncertain_content=evidence.uncertain_fragments,
            candidates=candidates[:3],
            clarification_question=None,
            clarification_options=[],
            requires_confirmation=True,
        )

    @staticmethod
    def _fallback_candidates(
        rejected: set[str],
    ) -> list[ExpressionCandidate]:
        fallback_texts = (
            "Hi, please call me back about a therapy appointment. Thanks.",
            "Hi, I’d like to speak with the therapy office. Please call me.",
        )
        return [
            ExpressionCandidate(
                id=f"lin-yue-scripted-fallback-{index + 1}",
                text=text,
                language="en",
                patient_supported_spans=["therapy", "call", "me", "back"],
                ai_added_spans=["fallback wording"],
                memory_support_ids=[],
                ranking_reasons=["scripted demonstration fallback"],
                risk_level=RiskLevel.ORDINARY,
                source_level="L2",
            )
            for index, text in enumerate(fallback_texts)
            if normalize(text) not in rejected
        ]
