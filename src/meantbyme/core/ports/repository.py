from typing import Protocol

from meantbyme.core.domain import (
    ExpressionReceipt,
    ExpressionSession,
    MemoryItem,
    MemoryWriteResult,
    RuntimeEvent,
)


class RepositoryPort(Protocol):
    def add_patient(self, patient_id: str, display_name: str) -> None: ...

    def create_session(
        self, patient_id: str, session: ExpressionSession
    ) -> None: ...

    def update_session(
        self, patient_id: str, session: ExpressionSession
    ) -> None: ...

    def append_event(self, patient_id: str, event: RuntimeEvent) -> None: ...

    def search_verified_memories(
        self, patient_id: str, fragments: list[str]
    ) -> list[MemoryItem]: ...

    def record_rejected_candidate(
        self, patient_id: str, candidate_id: str, text: str, session_id: str
    ) -> None: ...

    def write_verified_memory(
        self,
        patient_id: str,
        memory: MemoryItem,
        idempotency_key: str,
    ) -> MemoryWriteResult: ...

    def store_receipt(
        self, patient_id: str, receipt: ExpressionReceipt
    ) -> None: ...

    def has_active_voice_consent(
        self, patient_id: str, voice_profile_id: str
    ) -> bool: ...
