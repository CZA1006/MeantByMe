from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class ProviderRequestError(RuntimeError):
    def __init__(self, reason: str, *, status_code: int | None = None) -> None:
        super().__init__(reason)
        self.status_code = status_code


@dataclass(frozen=True)
class ProviderResponse:
    status_code: int
    body: bytes
    content_type: str


class ProviderHttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_attempts: int,
        backoff_seconds: float,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max(1, max_attempts)
        self._backoff_seconds = max(0.0, backoff_seconds)

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str],
    ) -> ProviderResponse:
        request_headers = {"Content-Type": "application/json", **headers}
        return self.request(
            url,
            body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=request_headers,
        )

    def request(
        self,
        url: str,
        *,
        body: bytes,
        headers: dict[str, str],
    ) -> ProviderResponse:
        last_error: ProviderRequestError | None = None
        for attempt in range(self._max_attempts):
            request = urllib.request.Request(
                url, data=body, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self._timeout_seconds
                ) as response:
                    return ProviderResponse(
                        status_code=response.status,
                        body=response.read(),
                        content_type=response.headers.get(
                            "Content-Type", "application/octet-stream"
                        ).split(";", 1)[0],
                    )
            except urllib.error.HTTPError as error:
                last_error = ProviderRequestError(
                    f"provider_http_{error.code}", status_code=error.code
                )
                if error.code != 429 and error.code < 500:
                    raise last_error from error
            except (TimeoutError, socket.timeout) as error:
                last_error = ProviderRequestError("provider_timeout")
            except urllib.error.URLError as error:
                last_error = ProviderRequestError("provider_unavailable")

            if attempt + 1 < self._max_attempts:
                time.sleep(self._backoff_seconds * (2**attempt))
        raise last_error or ProviderRequestError("provider_request_failed")
