from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class GatewaySettings:
    stepfun_api_key: str = field(default="", repr=False)
    openagents_api_key: str = field(default="", repr=False)
    gateway_token: str = field(default="", repr=False)
    rate_limit_per_minute: int = 120
    intent_provider: str = "stepfun"
    intent_model: str = "step-explore"
    provider_timeout_seconds: float = 20.0
    route_timeout_seconds: float = 30.0
    provider_max_attempts: int = 3
    retry_backoff_seconds: float = 0.5
    neutral_voice: str = "cixingnansheng"
    enable_voice_cloning: bool = False
    stepfun_base_url: str = "https://api.stepfun.com/step_plan/v1"
    openagents_base_url: str = "https://api-gateway.openagents.org/v1"

    def __post_init__(self) -> None:
        if self.provider_max_attempts < 3:
            object.__setattr__(self, "provider_max_attempts", 3)
        if self.rate_limit_per_minute < 1:
            object.__setattr__(self, "rate_limit_per_minute", 1)

    @classmethod
    def from_env(cls, *, load_local_env: bool = True) -> "GatewaySettings":
        if load_local_env:
            load_dotenv(override=False)
        provider = os.getenv("INTENT_PROVIDER", "stepfun").casefold()
        if provider not in {"openagents", "stepfun"}:
            raise ValueError("INTENT_PROVIDER must be openagents or stepfun")
        default_model = (
            "step-explore" if provider == "stepfun" else "deepseek-v4-pro"
        )
        return cls(
            stepfun_api_key=os.getenv("STEPFUN_API_KEY", ""),
            openagents_api_key=os.getenv("OPENAGENTS_API_KEY", ""),
            gateway_token=os.getenv("GATEWAY_TOKEN", ""),
            rate_limit_per_minute=max(
                1,
                int(os.getenv("GATEWAY_RATE_LIMIT_PER_MINUTE", "120")),
            ),
            intent_provider=provider,
            intent_model=os.getenv("INTENT_MODEL", default_model),
            provider_timeout_seconds=float(
                os.getenv("PROVIDER_TIMEOUT_SECONDS", "20")
            ),
            route_timeout_seconds=float(
                os.getenv("ROUTE_TIMEOUT_SECONDS", "30")
            ),
            provider_max_attempts=max(
                3, int(os.getenv("PROVIDER_MAX_ATTEMPTS", "3"))
            ),
            retry_backoff_seconds=max(
                0.0, float(os.getenv("RETRY_BACKOFF_SECONDS", "0.5"))
            ),
            neutral_voice=os.getenv(
                "STEPFUN_NEUTRAL_VOICE", "cixingnansheng"
            ),
            enable_voice_cloning=_env_flag("ENABLE_VOICE_CLONING"),
            stepfun_base_url=os.getenv(
                "STEPFUN_BASE_URL",
                "https://api.stepfun.com/step_plan/v1",
            ).rstrip("/"),
            openagents_base_url=os.getenv(
                "OPENAGENTS_BASE_URL",
                "https://api-gateway.openagents.org/v1",
            ).rstrip("/"),
        )


def _env_flag(name: str) -> bool:
    return os.getenv(name, "false").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }
