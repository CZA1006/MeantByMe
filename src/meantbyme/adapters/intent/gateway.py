from __future__ import annotations

from pydantic import ValidationError

from meantbyme.adapters.http import GatewayError, GatewayHttpClient
from meantbyme.adapters.intent.template import TemplateIntentAdapter
from meantbyme.core.domain import (
    ConfirmedContext,
    IntentProposal,
    MemoryItem,
    TranscriptEvidence,
)
from meantbyme.core.personalization.text import normalize, tokenize


class GatewayIntentAdapter:
    def __init__(
        self,
        *,
        client: GatewayHttpClient,
        patient_id: str,
        session_id: str,
        fallback: TemplateIntentAdapter | None = None,
    ) -> None:
        self._client = client
        self._patient_id = patient_id
        self._session_id = session_id
        self._fallback = fallback or TemplateIntentAdapter()

    def propose(
        self,
        evidence: TranscriptEvidence,
        memories: list[MemoryItem],
        confirmed_context: ConfirmedContext,
    ) -> IntentProposal:
        payload = {
            "patient_id": self._patient_id,
            "session_id": self._session_id,
            "language": next(
                (
                    result.language
                    for result in evidence.results
                    if result.language
                ),
                None,
            ),
            "evidence": evidence.model_dump(mode="json"),
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
                for memory in memories
            ],
            "confirmed_context": confirmed_context.model_dump(mode="json"),
        }
        try:
            response = self._client.post_json("/v1/intent/propose", payload)
            proposal = IntentProposal.model_validate(
                response.get("proposal", response)
            )
            self._validate_contract(proposal, confirmed_context)
            return proposal
        except (GatewayError, ValidationError, ValueError, TypeError):
            return self._fallback.propose(
                evidence, memories, confirmed_context
            )

    @staticmethod
    def _validate_contract(
        proposal: IntentProposal, context: ConfirmedContext
    ) -> None:
        if not proposal.requires_confirmation:
            raise ValueError("Cloud proposal attempted to skip confirmation")
        if not 2 <= len(proposal.candidates) <= 3:
            raise ValueError("Cloud proposal must contain two or three candidates")
        normalized = [normalize(item.text) for item in proposal.candidates]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Cloud proposal candidates must be distinct")
        locked = {normalize(token) for token in context.locked_tokens}
        for candidate in proposal.candidates:
            if not locked.issubset(set(tokenize(candidate.text))):
                raise ValueError("Cloud proposal dropped confirmed tokens")
