from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class DesktopSettings:
    gateway_url: str = "http://127.0.0.1:8000"
    gateway_token: str = field(default="", repr=False)
    gateway_timeout_seconds: float = 8.0
    gateway_max_attempts: int = 2
    audio_store_dir: Path = Path("artifacts/audio")

    @classmethod
    def from_env(cls) -> "DesktopSettings":
        load_dotenv(override=False)
        return cls(
            gateway_url=os.getenv(
                "GATEWAY_URL", "http://127.0.0.1:8000"
            ).rstrip("/"),
            gateway_token=os.getenv("GATEWAY_TOKEN", ""),
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
