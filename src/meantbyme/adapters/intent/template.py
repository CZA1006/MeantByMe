from __future__ import annotations

from meantbyme.core.domain import (
    ConfirmedContext,
    ExpressionCandidate,
    IntentProposal,
    MemoryItem,
    RiskLevel,
    TranscriptEvidence,
)
from meantbyme.core.personalization.text import normalize, tokenize


class TemplateIntentAdapter:
    """Deterministic degraded-mode candidates that preserve confirmed content."""

    def propose(
        self,
        evidence: TranscriptEvidence,
        memories: list[MemoryItem],
        confirmed_context: ConfirmedContext,
    ) -> IntentProposal:
        del memories
        supported = list(
            dict.fromkeys(
                confirmed_context.locked_tokens
                or evidence.stable_fragments
                or evidence.uncertain_fragments
            )
        )
        required_tokens = list(supported)
        for value in confirmed_context.locked_slots.values():
            for token in tokenize(value):
                if token not in required_tokens:
                    required_tokens.append(token)

        prefix = " ".join(required_tokens).strip()
        if prefix:
            prefix = prefix[0].upper() + prefix[1:]
        else:
            prefix = "I need help communicating"

        rejected = {
            normalize(text) for text in confirmed_context.rejected_texts
        }
        language = next(
            (
                result.language
                for result in evidence.results
                if result.language
            ),
            "en",
        )
        candidates = []
        alternative = len(rejected) + 1
        while len(candidates) < 3:
            suffix = (
                "Please help me finish this thought using "
                f"alternative {alternative}."
            )
            text = f"{prefix}. {suffix}"
            if normalize(text) in rejected:
                alternative += 1
                continue
            candidate = ExpressionCandidate(
                id=f"template-c{alternative}",
                text=text,
                language=language,
                patient_supported_spans=supported,
                ai_added_spans=[suffix],
                memory_support_ids=[],
                ranking_reasons=["deterministic template fallback"],
                risk_level=RiskLevel.ORDINARY,
                source_level="L2",
            )
            self._assert_locked(candidate, confirmed_context)
            candidates.append(candidate)
            alternative += 1
        return IntentProposal(
            certain_content=supported,
            uncertain_content=evidence.uncertain_fragments,
            candidates=candidates[:3],
            clarification_question=None,
            clarification_options=[],
            requires_confirmation=True,
        )

    @staticmethod
    def _assert_locked(
        candidate: ExpressionCandidate, context: ConfirmedContext
    ) -> None:
        candidate_tokens = set(tokenize(candidate.text))
        required = {
            part
            for locked_token in context.locked_tokens
            for part in tokenize(locked_token)
        }
        for value in context.locked_slots.values():
            required.update(tokenize(value))
        if not required.issubset(candidate_tokens):
            raise ValueError("Template candidate dropped confirmed context")
