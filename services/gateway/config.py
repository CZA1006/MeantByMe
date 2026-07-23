from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class GatewaySettings:
    stepfun_api_key: str = field(default="", repr=False)
    openagents_api_key: str = field(default="", repr=False)
    intent_provider: str = "openagents"
    intent_model: str = "deepseek-v4-pro"
    provider_timeout_seconds: float = 20.0
    route_timeout_seconds: float = 30.0
    provider_max_attempts: int = 3
    retry_backoff_seconds: float = 0.5
    neutral_voice: str = "cixingnansheng"
    stepfun_base_url: str = "https://api.stepfun.com/v1"
    openagents_base_url: str = "https://api-gateway.openagents.org/v1"

    @classmethod
    def from_env(cls, *, load_local_env: bool = True) -> "GatewaySettings":
        if load_local_env:
            load_dotenv(override=False)
        provider = os.getenv("INTENT_PROVIDER", "openagents").casefold()
        if provider not in {"openagents", "stepfun"}:
            raise ValueError("INTENT_PROVIDER must be openagents or stepfun")
        default_model = (
            "step-explore" if provider == "stepfun" else "deepseek-v4-pro"
        )
        return cls(
            stepfun_api_key=os.getenv("STEPFUN_API_KEY", ""),
            openagents_api_key=os.getenv("OPENAGENTS_API_KEY", ""),
            intent_provider=provider,
            intent_model=os.getenv("INTENT_MODEL", default_model),
            provider_timeout_seconds=float(
                os.getenv("PROVIDER_TIMEOUT_SECONDS", "20")
            ),
            route_timeout_seconds=float(
                os.getenv("ROUTE_TIMEOUT_SECONDS", "30")
            ),
            provider_max_attempts=max(
                1, int(os.getenv("PROVIDER_MAX_ATTEMPTS", "3"))
            ),
            retry_backoff_seconds=max(
                0.0, float(os.getenv("RETRY_BACKOFF_SECONDS", "0.5"))
            ),
            neutral_voice=os.getenv(
                "STEPFUN_NEUTRAL_VOICE", "cixingnansheng"
            ),
            stepfun_base_url=os.getenv(
                "STEPFUN_BASE_URL", "https://api.stepfun.com/v1"
            ).rstrip("/"),
            openagents_base_url=os.getenv(
                "OPENAGENTS_BASE_URL",
                "https://api-gateway.openagents.org/v1",
            ).rstrip("/"),
        )
