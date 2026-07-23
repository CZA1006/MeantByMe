from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DesktopSettings:
    gateway_url: str = "http://127.0.0.1:8000"
    gateway_timeout_seconds: float = 8.0
    gateway_max_attempts: int = 2
    audio_store_dir: Path = Path("artifacts/audio")

    @classmethod
    def from_env(cls) -> "DesktopSettings":
        return cls(
            gateway_url=os.getenv(
                "GATEWAY_URL", "http://127.0.0.1:8000"
            ).rstrip("/"),
            gateway_timeout_seconds=float(
                os.getenv("GATEWAY_TIMEOUT_SECONDS", "8")
            ),
            gateway_max_attempts=max(
                1, int(os.getenv("GATEWAY_MAX_ATTEMPTS", "2"))
            ),
            audio_store_dir=Path(
                os.getenv("AUDIO_STORE_DIR", "artifacts/audio")
            ),
        )
