from meantbyme.core.domain import (
    ConfirmedContext,
    ExpressionCandidate,
    IntentProposal,
    MemoryItem,
    RiskLevel,
    TranscriptEvidence,
)
from meantbyme.core.personalization.text import normalize, tokenize


class MockIntentAdapter:
    def propose(
        self,
        evidence: TranscriptEvidence,
        memories: list[MemoryItem],
        confirmed_context: ConfirmedContext,
    ) -> IntentProposal:
        round_number = 2 if confirmed_context.rejected_texts else 1
        supported = confirmed_context.locked_tokens or evidence.stable_fragments
        memory_by_text = {
            normalize(memory.text): memory.id
            for memory in memories
            if memory.text
        }

        if round_number == 1:
            templates = [
                ("I don't want to go tomorrow.", ["want to go"]),
                ("I don't want to move the plan tomorrow.", ["want to move the plan"]),
                ("I don't want to meet anyone tomorrow.", ["want to meet anyone"]),
            ]
        else:
            templates = [
                ("I don't need to go tomorrow.", ["need to go"]),
                ("I don't plan to call tomorrow.", ["plan to call"]),
                ("I don't want an appointment tomorrow.", ["want an appointment"]),
            ]

        rejected = {normalize(text) for text in confirmed_context.rejected_texts}
        candidates: list[ExpressionCandidate] = []
        for index, (text, ai_spans) in enumerate(templates):
            if normalize(text) in rejected:
                continue
            memory_id = memory_by_text.get(normalize(text))
            candidate = ExpressionCandidate(
                id=f"mock-r{round_number}-c{index + 1}",
                text=text,
                language="en",
                patient_supported_spans=list(supported),
                ai_added_spans=ai_spans,
                memory_support_ids=[memory_id] if memory_id else [],
                ranking_reasons=[
                    "strong fragment support",
                    *(
                        ["matched verified patient phrase"]
                        if memory_id
                        else []
                    ),
                ],
                risk_level=RiskLevel.ORDINARY,
                source_level="L2",
            )
            self._assert_confirmed_context(candidate, confirmed_context)
            candidates.append(candidate)

        return IntentProposal(
            certain_content=list(supported),
            uncertain_content=evidence.uncertain_fragments,
            candidates=candidates[:3],
            clarification_question=None,
            clarification_options=[],
            requires_confirmation=True,
        )

    @staticmethod
    def _assert_confirmed_context(
        candidate: ExpressionCandidate, context: ConfirmedContext
    ) -> None:
        candidate_tokens = set(tokenize(candidate.text))
        required = {
            part
            for locked_token in context.locked_tokens
            for part in tokenize(locked_token)
        }
        if not required.issubset(candidate_tokens):
            raise ValueError("Candidate dropped locked confirmed context")
        if normalize(candidate.text) in {
            normalize(text) for text in context.rejected_texts
        }:
            raise ValueError("Candidate repeated a rejected expression")
