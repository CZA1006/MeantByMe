from __future__ import annotations

from pydantic import ValidationError

from meantbyme.adapters.http import GatewayError, GatewayHttpClient
from meantbyme.core.domain import CommandIntent, CommandInterpretation


class GatewayCommandIntentAdapter:
    def __init__(
        self,
        client: GatewayHttpClient,
    ) -> None:
        self._client = client

    def interpret(
        self, transcript: str, *, stage: str, language: str | None
    ) -> CommandInterpretation:
        try:
            payload = self._client.post_json(
                "/v1/commands/interpret",
                {
                    "transcript": transcript,
                    "stage": stage,
                    "language": language,
                },
            )
            return CommandInterpretation.model_validate(payload)
        except (GatewayError, ValidationError, TypeError, ValueError) as error:
            return CommandInterpretation(
                provider="gateway_command_intent",
                transcript=transcript,
                intent=CommandIntent.UNKNOWN,
                status="failed",
                error=type(error).__name__,
            )
