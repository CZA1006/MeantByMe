from typing import Protocol

from meantbyme.core.domain import (
    ASRResult,
    AuthorizedExpression,
    CommandInterpretation,
    ConfirmedContext,
    ExpressionCandidate,
    IntentProposal,
    MemoryItem,
    TranscriptEvidence,
    TTSResult,
)


class ASRPort(Protocol):
    def transcribe(self, audio_id: str) -> list[ASRResult]:
        """Return validated primary and secondary transcript evidence."""


class IntentPort(Protocol):
    def propose(
        self,
        evidence: TranscriptEvidence,
        memories: list[MemoryItem],
        confirmed_context: ConfirmedContext,
        situation: str | None = None,
    ) -> IntentProposal:
        """Propose candidates without selecting, authorizing, or writing memory."""


class CommandIntentPort(Protocol):
    def interpret(
        self, transcript: str, *, stage: str, language: str | None
    ) -> CommandInterpretation:
        """Classify a command without authorizing voice or writing memory."""


class TTSPort(Protocol):
    def synthesize_neutral(self, candidate: ExpressionCandidate) -> TTSResult:
        """Create a non-personal private readback for a candidate."""

    def synthesize_personal(
        self, expression: AuthorizedExpression
    ) -> TTSResult:
        """Synthesize personal voice from a one-time authorization object only."""
