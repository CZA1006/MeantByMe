from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class GatewayError(RuntimeError):
    pass


class GatewayTimeout(GatewayError):
    pass


class GatewayHTTPError(GatewayError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"Gateway returned HTTP {status_code}")
        self.status_code = status_code


class GatewayInvalidResponse(GatewayError):
    pass


@dataclass(frozen=True)
class GatewayResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]


class GatewayHttpClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 35.0,
        max_attempts: int = 2,
        backoff_seconds: float = 0.1,
        token: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max(1, max_attempts)
        self._backoff_seconds = max(0.0, backoff_seconds)
        self._token = token

    def post_json(
        self, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        response = self.request(
            "POST",
            path,
            body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            parsed = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GatewayInvalidResponse("Gateway returned invalid JSON") from error
        if not isinstance(parsed, dict):
            raise GatewayInvalidResponse("Gateway JSON must be an object")
        return parsed

    def post_wav(
        self,
        path: str,
        wav_bytes: bytes,
        *,
        headers: dict[str, str] | None = None,
    ) -> GatewayResponse:
        request_headers = {
            "Content-Type": "audio/wav",
            "Accept": "application/json",
        }
        request_headers.update(headers or {})
        return self.request(
            "POST", path, body=wav_bytes, headers=request_headers
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> GatewayResponse:
        last_error: GatewayError | None = None
        for attempt in range(self._max_attempts):
            request_headers = dict(headers or {})
            if self._token:
                request_headers["X-Gateway-Token"] = self._token
            request = urllib.request.Request(
                f"{self._base_url}{path}",
                data=body,
                headers=request_headers,
                method=method,
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self._timeout_seconds
                ) as response:
                    return GatewayResponse(
                        status_code=response.status,
                        body=response.read(),
                        headers={
                            key.casefold(): value
                            for key, value in response.headers.items()
                        },
                    )
            except urllib.error.HTTPError as error:
                last_error = GatewayHTTPError(error.code)
                if error.code != 429 and error.code < 500:
                    raise last_error from error
            except (TimeoutError, socket.timeout) as error:
                last_error = GatewayTimeout("Gateway request timed out")
            except urllib.error.URLError as error:
                if isinstance(error.reason, (TimeoutError, socket.timeout)):
                    last_error = GatewayTimeout("Gateway request timed out")
                else:
                    last_error = GatewayError("Gateway is unavailable")

            if attempt + 1 < self._max_attempts:
                time.sleep(self._backoff_seconds * (2**attempt))
        raise last_error or GatewayError("Gateway request failed")
