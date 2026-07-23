import base64
import json
from pathlib import Path

from meantbyme.core.domain import (
    AuthorizedExpression,
    ExpressionCandidate,
    TTSResult,
)


class CachedTTSAdapter:
    def __init__(
        self,
        neutral_audio_path: Path,
        personal_audio_path: Path,
        *,
        fail_personal: bool = False,
        fail_neutral: bool = False,
    ) -> None:
        self._neutral_audio_path = neutral_audio_path
        self._personal_audio_path = personal_audio_path
        self._fail_personal = fail_personal
        self._fail_neutral = fail_neutral
        self._consumed_authorizations: set[tuple[str, str]] = set()
        self.personal_calls = 0

    def synthesize_neutral(
        self, candidate: ExpressionCandidate
    ) -> TTSResult:
        if self._fail_neutral:
            return TTSResult(status="failed", error="simulated neutral TTS failure")
        return self._read_cache(self._neutral_audio_path, "neutral")

    def synthesize_personal(
        self, expression: AuthorizedExpression
    ) -> TTSResult:
        if not isinstance(expression, AuthorizedExpression):
            raise TypeError(
                "Personal TTS requires an AuthorizedExpression object"
            )
        self.personal_calls += 1
        authorization_key = (
            expression.session_id,
            expression.authorized_at.isoformat(),
        )
        if authorization_key in self._consumed_authorizations:
            return TTSResult(
                status="failed", error="authorization already consumed"
            )
        if self._fail_personal:
            return TTSResult(
                status="failed", error="simulated personal TTS failure"
            )
        result = self._read_cache(self._personal_audio_path, "personal")
        if result.status == "failed":
            return result
        self._consumed_authorizations.add(authorization_key)
        return result

    @staticmethod
    def _read_cache(path: Path, voice: str) -> TTSResult:
        if not path.is_file():
            return TTSResult(status="failed", error=f"{voice} cache missing")
        try:
            payload = json.loads(path.read_text(encoding="ascii"))
            audio_bytes = base64.b64decode(payload["data"], validate=True)
        except (KeyError, ValueError, json.JSONDecodeError) as error:
            return TTSResult(
                status="failed",
                error=f"invalid {voice} audio cache: {type(error).__name__}",
            )
        if not audio_bytes.startswith(b"RIFF"):
            return TTSResult(
                status="failed", error=f"invalid {voice} WAV cache"
            )
        return TTSResult(
            status="success",
            audio_path=str(path),
            audio_bytes=audio_bytes,
            media_type=payload.get("media_type", "audio/wav"),
        )
