import json
from pathlib import Path
from typing import Any

from meantbyme.core.domain import ASRResult


class MockASRAdapter:
    def __init__(self, fixtures: dict[str, list[dict[str, Any]]]) -> None:
        self._fixtures = fixtures

    @classmethod
    def from_json(cls, path: Path) -> "MockASRAdapter":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(payload["audio_fixtures"])

    def transcribe(self, audio_id: str) -> list[ASRResult]:
        if audio_id not in self._fixtures:
            raise KeyError(f"No mock ASR fixture for audio_id={audio_id}")
        return [
            ASRResult.model_validate(item)
            for item in self._fixtures[audio_id]
        ]
