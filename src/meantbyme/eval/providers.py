from __future__ import annotations

import json
from pathlib import Path

from meantbyme.core.domain import (
    ASRResult,
    ConfirmedContext,
    ExpressionCandidate,
    IntentProposal,
    MemoryItem,
    RiskLevel,
    TranscriptEvidence,
)
from meantbyme.eval.models import EvaluationSample
from meantbyme.eval.text import eval_tokens, normalize_for_eval


class EvaluationIntentAdapter:
    """Deterministic sample fixture; it proposes but never selects or authorizes."""

    def __init__(self, sample: EvaluationSample) -> None:
        self._sample = sample

    def propose(
        self,
        evidence: TranscriptEvidence,
        memories: list[MemoryItem],
        confirmed_context: ConfirmedContext,
    ) -> IntentProposal:
        del evidence
        texts = self._candidate_texts(confirmed_context)
        candidates = [
            self._candidate(index, text, memories, confirmed_context)
            for index, text in enumerate(texts)
        ]
        return IntentProposal(
            certain_content=list(confirmed_context.locked_tokens),
            uncertain_content=[],
            candidates=candidates,
            clarification_question=None,
            clarification_options=[],
            requires_confirmation=True,
        )

    def _candidate_texts(
        self, confirmed_context: ConfirmedContext
    ) -> list[str]:
        target = self._sample.intended_expression
        base = target.rstrip(" .!?。！？")
        compact = (
            " ".join(confirmed_context.locked_tokens).strip()
            + ("." if self._sample.language.startswith("en") else "。")
        )
        suffixes = (
            [
                f"{base}, please confirm.",
                f"{base}, but not yet.",
                f"{base}, if that is possible.",
                f"{base}, in that context.",
                f"{base}, please ask again.",
            ]
            if self._sample.language.casefold().startswith("en")
            else [
                f"{base}，请再确认。",
                f"{base}，但不是现在。",
                f"{base}，如果可以。",
                f"{base}，就是这个情景。",
                f"{base}，请再问一次。",
            ]
        )
        possible = [
            target,
            *([compact] if confirmed_context.locked_tokens else []),
            *(memory.text for memory in self._sample.seed_memories),
            *suffixes,
        ]
        rejected = {
            normalize_for_eval(text)
            for text in confirmed_context.rejected_texts
        }
        unique: list[str] = []
        seen: set[str] = set()
        for text in possible:
            normalized = normalize_for_eval(text)
            if normalized in seen or normalized in rejected:
                continue
            seen.add(normalized)
            unique.append(text)

        if self._sample.memory_expected_to_help and len(unique) > 1:
            target_normalized = normalize_for_eval(target)
            target_item = next(
                item
                for item in unique
                if normalize_for_eval(item) == target_normalized
            )
            unique.remove(target_item)
            unique.insert(1, target_item)
        return unique[:3]

    def _candidate(
        self,
        index: int,
        text: str,
        memories: list[MemoryItem],
        confirmed_context: ConfirmedContext,
    ) -> ExpressionCandidate:
        target_match = normalize_for_eval(text) == normalize_for_eval(
            self._sample.intended_expression
        )
        memory_ids = [
            memory.id
            for memory in memories
            if memory.text
            and normalize_for_eval(memory.text) == normalize_for_eval(text)
        ]
        supported = list(confirmed_context.locked_tokens)
        supported_tokens = {
            token
            for span in supported
            for token in eval_tokens(span)
        }
        added = [
            token
            for token in eval_tokens(text)
            if token not in supported_tokens
        ]
        if self._sample.category == "complete_speech":
            source_level = "L1"
        elif self._sample.category == "unknown_phrase":
            source_level = "L3"
        else:
            source_level = "L2"
        return ExpressionCandidate(
            id=f"{self._sample.sample_id}-candidate-{index + 1}",
            text=text,
            language=self._sample.language,
            patient_supported_spans=supported,
            ai_added_spans=added,
            memory_support_ids=memory_ids,
            ranking_reasons=[
                "simulated evaluation fixture",
                (
                    "matches annotated intended expression"
                    if target_match
                    else "distinct recovery alternative"
                ),
            ],
            risk_level=(
                self._sample.risk_level
                if target_match
                else RiskLevel.ORDINARY
            ),
            source_level=source_level if target_match else "L3",
        )


class ReplayASRAdapter:
    def __init__(self, recording_path: Path) -> None:
        payload = json.loads(recording_path.read_text(encoding="utf-8"))
        if payload.get("simulated") is not True:
            raise ValueError("Replay fixtures must declare simulated=true")
        self._results = [
            ASRResult.model_validate(item)
            for item in payload["asr_results"]
        ]

    def transcribe(self, audio_id: str) -> list[ASRResult]:
        del audio_id
        return [result.model_copy(deep=True) for result in self._results]


class ReplayIntentAdapter:
    def __init__(self, recording_path: Path) -> None:
        payload = json.loads(recording_path.read_text(encoding="utf-8"))
        if payload.get("simulated") is not True:
            raise ValueError("Replay fixtures must declare simulated=true")
        proposals = payload.get("intent_proposals")
        if proposals is None:
            proposals = [payload["intent_proposal"]]
        self._proposals = [
            IntentProposal.model_validate(item) for item in proposals
        ]
        self._next = 0

    def propose(
        self,
        evidence: TranscriptEvidence,
        memories: list[MemoryItem],
        confirmed_context: ConfirmedContext,
    ) -> IntentProposal:
        del evidence, memories, confirmed_context
        proposal = self._proposals[min(self._next, len(self._proposals) - 1)]
        self._next += 1
        return proposal.model_copy(deep=True)
