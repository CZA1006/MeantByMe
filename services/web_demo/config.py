from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class WebDemoSettings:
    mode: str = "mock"
    demo_token: str = field(default="", repr=False)
    gateway_url: str = "http://127.0.0.1:8000"
    gateway_token: str = field(default="", repr=False)
    gateway_timeout_seconds: float = 35.0
    gateway_max_attempts: int = 2
    voice_profile_id: str = "cixingnansheng"
    audio_store_root: Path = Path(tempfile.gettempdir()) / "meantbyme-web-demo"
    max_audio_bytes: int = 16 * 1024 * 1024
    max_audio_seconds: float = 20.0
    max_sessions: int = 100

    @classmethod
    def from_env(cls) -> "WebDemoSettings":
        load_dotenv(override=False)
        mode = os.getenv("WEB_DEMO_MODE", "mock").strip().lower()
        if mode not in {"mock", "cloud"}:
            raise ValueError("WEB_DEMO_MODE must be mock or cloud")
        return cls(
            mode=mode,
            demo_token=os.getenv("WEB_DEMO_TOKEN", ""),
            gateway_url=os.getenv(
                "GATEWAY_URL", "http://127.0.0.1:8000"
            ).rstrip("/"),
            gateway_token=os.getenv("GATEWAY_TOKEN", ""),
            gateway_timeout_seconds=float(
                os.getenv("GATEWAY_TIMEOUT_SECONDS", "35")
            ),
            gateway_max_attempts=max(
                1, int(os.getenv("GATEWAY_MAX_ATTEMPTS", "2"))
            ),
            voice_profile_id=os.getenv(
                "WEB_DEMO_VOICE_PROFILE_ID", "cixingnansheng"
            ),
            audio_store_root=Path(
                os.getenv(
                    "WEB_DEMO_AUDIO_DIR",
                    str(Path(tempfile.gettempdir()) / "meantbyme-web-demo"),
                )
            ),
            max_audio_bytes=max(
                1,
                int(
                    os.getenv(
                        "WEB_DEMO_MAX_AUDIO_BYTES",
                        str(16 * 1024 * 1024),
                    )
                ),
            ),
            max_audio_seconds=max(
                0.1,
                float(os.getenv("WEB_DEMO_MAX_AUDIO_SECONDS", "20")),
            ),
            max_sessions=max(
                1, int(os.getenv("WEB_DEMO_MAX_SESSIONS", "100"))
            ),
        )
