from __future__ import annotations

import urllib.request
from typing import Any

import pytest
from fastapi.testclient import TestClient

from meantbyme.adapters.http import GatewayHttpClient
from meantbyme.config import DesktopSettings
from services.gateway.app import create_app
from services.gateway.config import GatewaySettings


TOKEN = "test-gateway-token"
INTENT_PAYLOAD = {
    "patient_id": "patient-test",
    "session_id": "session-test",
    "language": "en",
    "situation": None,
    "evidence": {},
    "memories": [],
    "confirmed_context": {},
}


class RecordingGatewayProvider:
    def __init__(self) -> None:
        self.intent_calls: list[dict[str, Any]] = []

    def propose_intent(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.intent_calls.append(payload)
        return {"provider": "recording"}


def _client(
    *,
    token: str = TOKEN,
    rate_limit: int = 120,
    provider: RecordingGatewayProvider | None = None,
) -> TestClient:
    return TestClient(
        create_app(
            settings=GatewaySettings(
                gateway_token=token,
                rate_limit_per_minute=rate_limit,
            ),
            providers=provider or RecordingGatewayProvider(),
        )
    )


@pytest.mark.parametrize(
    ("path", "kwargs"),
    [
        (
            "/v1/asr/primary",
            {
                "content": b"",
                "headers": {
                    "X-Patient-Id": "patient-test",
                    "X-Session-Id": "session-test",
                },
            },
        ),
        ("/v1/intent/propose", {"json": INTENT_PAYLOAD}),
        (
            "/v1/tts/synthesize",
            {
                "json": {
                    "text": "hello",
                    "mode": "neutral",
                    "scope": "preview",
                }
            },
        ),
        (
            "/v1/tts/enroll-voice",
            {
                "content": b"",
                "headers": {
                    "X-Patient-Id": "patient-test",
                    "X-Session-Id": "session-test",
                },
            },
        ),
    ],
)
def test_all_provider_routes_reject_missing_token(
    path: str, kwargs: dict[str, Any]
) -> None:
    response = _client().post(path, **kwargs)

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid gateway token"}


def test_wrong_token_is_rejected() -> None:
    response = _client().post(
        "/v1/intent/propose",
        json=INTENT_PAYLOAD,
        headers={"X-Gateway-Token": "wrong-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid gateway token"}


def test_correct_token_reaches_provider() -> None:
    provider = RecordingGatewayProvider()
    response = _client(provider=provider).post(
        "/v1/intent/propose",
        json=INTENT_PAYLOAD,
        headers={"X-Gateway-Token": TOKEN},
    )

    assert response.status_code == 200
    assert response.json() == {"provider": "recording"}
    assert provider.intent_calls == [INTENT_PAYLOAD]


def test_unconfigured_gateway_fails_closed_but_health_is_public() -> None:
    client = _client(token="")

    protected = client.post(
        "/v1/intent/propose",
        json=INTENT_PAYLOAD,
    )
    health = client.get("/v1/health")

    assert protected.status_code == 503
    assert protected.json() == {
        "detail": "gateway token not configured"
    }
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_health_never_requires_or_exposes_credentials() -> None:
    settings = GatewaySettings(
        gateway_token="gateway-secret-value",
        stepfun_api_key="stepfun-secret-value",
        openagents_api_key="openagents-secret-value",
    )
    response = TestClient(
        create_app(
            settings=settings,
            providers=RecordingGatewayProvider(),
        )
    ).get("/v1/health")

    body = response.text
    assert response.status_code == 200
    assert "gateway-secret-value" not in body
    assert "stepfun-secret-value" not in body
    assert "openagents-secret-value" not in body
    assert "gateway_token" not in body


def test_rate_limiter_allows_limit_then_returns_429() -> None:
    provider = RecordingGatewayProvider()
    client = _client(rate_limit=2, provider=provider)
    headers = {"X-Gateway-Token": TOKEN}

    responses = [
        client.post(
            "/v1/intent/propose",
            json=INTENT_PAYLOAD,
            headers=headers,
        )
        for _ in range(3)
    ]

    assert [response.status_code for response in responses] == [200, 200, 429]
    assert responses[-1].json() == {"detail": "rate limited"}
    assert len(provider.intent_calls) == 2


class _HTTPResponse:
    status = 200
    headers: dict[str, str] = {}

    def __enter__(self) -> "_HTTPResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b"{}"


def test_desktop_client_sends_configured_token_and_omits_empty_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[urllib.request.Request] = []

    def fake_urlopen(
        request: urllib.request.Request, *, timeout: float
    ) -> _HTTPResponse:
        del timeout
        requests.append(request)
        return _HTTPResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    GatewayHttpClient(
        "http://gateway.test",
        token=TOKEN,
    ).request("GET", "/v1/health")
    GatewayHttpClient("http://gateway.test").request(
        "GET", "/v1/health"
    )

    configured_headers = {
        key.casefold(): value for key, value in requests[0].header_items()
    }
    empty_headers = {
        key.casefold(): value for key, value in requests[1].header_items()
    }
    assert configured_headers["x-gateway-token"] == TOKEN
    assert "x-gateway-token" not in empty_headers


def test_gateway_and_desktop_settings_load_token_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GATEWAY_TOKEN", TOKEN)
    monkeypatch.setenv("GATEWAY_RATE_LIMIT_PER_MINUTE", "17")

    gateway = GatewaySettings.from_env(load_local_env=False)
    desktop = DesktopSettings.from_env()

    assert gateway.gateway_token == TOKEN
    assert gateway.rate_limit_per_minute == 17
    assert desktop.gateway_token == TOKEN
    assert TOKEN not in repr(gateway)
    assert TOKEN not in repr(desktop)
