from __future__ import annotations

import threading

from meantbyme.core.domain import ASRResult
from meantbyme.core.ports import ASRPort


class HeadsetPrimaryASRAdapter:
    """Combines a trusted headset text stream with server-side audio ASR."""

    def __init__(self, delegate: ASRPort) -> None:
        self._delegate = delegate
        self._pending: dict[str, tuple[str, str | None]] = {}
        self._lock = threading.RLock()

    def submit_primary(
        self,
        audio_id: str,
        transcript: str,
        *,
        language: str | None,
    ) -> None:
        normalized = transcript.strip()
        if not normalized:
            return
        with self._lock:
            self._pending[audio_id] = (normalized, language)

    def transcribe(self, audio_id: str) -> list[ASRResult]:
        with self._lock:
            primary = self._pending.pop(audio_id, None)
        remote_results = self._delegate.transcribe(audio_id)
        if primary is None:
            return remote_results
        transcript, language = primary
        return [
            ASRResult(
                provider="viaim_ios_primary",
                transcript=transcript,
                language=language,
                segments=[],
                latency_ms=None,
                status="success",
            ),
            *remote_results,
        ]
