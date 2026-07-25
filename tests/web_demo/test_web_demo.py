from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from meantbyme.core.domain import RuntimeEventType, SessionStage
from services.web_demo.app import create_app
from services.web_demo.config import WebDemoSettings
from tests.helpers.stub_gateway import (
    StubGatewayState,
    running_stub_gateway,
    wav_bytes,
)


DEMO_TOKEN = "test-demo-access"


def _settings(tmp_path: Path, **updates) -> WebDemoSettings:
    values = {
        "mode": "mock",
        "demo_token": DEMO_TOKEN,
        "audio_store_root": tmp_path / "web-audio",
    }
    values.update(updates)
    return WebDemoSettings(**values)


def _create_session(
    client: TestClient,
) -> tuple[dict, dict[str, str]]:
    response = client.post(
        "/api/sessions",
        headers={"X-Demo-Token": DEMO_TOKEN},
        json={"language": "en", "profile_ref": "david_demo"},
    )
    assert response.status_code == 200
    payload = response.json()
    headers = {
        "X-Demo-Token": DEMO_TOKEN,
        "X-Demo-Session": payload["session_token"],
    }
    return payload, headers


def _command(
    client: TestClient,
    session_id: str,
    headers: dict[str, str],
    command: str,
    *,
    payload: dict | None = None,
    confirmation_method: str | None = None,
) -> dict:
    response = client.post(
        f"/api/sessions/{session_id}/commands",
        headers=headers,
        json={
            "command": command,
            "payload": payload or {},
            "confirmation_method": confirmation_method,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _drive_to_candidates(
    client: TestClient,
    session_id: str,
    headers: dict[str, str],
) -> dict:
    _command(client, session_id, headers, "start_capture")
    heard = _command(client, session_id, headers, "stop_capture")
    assert heard["session"]["stage"] == SessionStage.HEARD_CONTENT_REVIEW
    assert heard["session"]["heard_sequence"]
    assert {
        token["status"] for token in heard["session"]["heard_sequence"]
    }.issubset({"stable", "uncertain"})
    routed = _command(
        client, session_id, headers, "confirm_heard_content"
    )
    if routed["session"]["stage"] == SessionStage.CATEGORY_CLARIFICATION:
        routed = _command(
            client,
            session_id,
            headers,
            "select_category",
            payload={"category": "plan"},
        )
    assert routed["session"]["stage"] in {
        SessionStage.CANDIDATE_SELECTION,
        SessionStage.FINAL_REVIEW,
    }
    return routed


def test_health_and_page_are_public_but_sessions_require_demo_token(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        health = client.get("/api/health")
        page = client.get("/")
        missing = client.post("/api/sessions", json={"language": "en"})
        wrong = client.post(
            "/api/sessions",
            headers={"X-Demo-Token": "wrong"},
            json={"language": "en"},
        )

    assert health.status_code == 200
    assert health.json()["simulated"] is True
    assert health.json()["max_audio_seconds"] == 20.0
    assert DEMO_TOKEN not in health.text
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store, max-age=0"
    assert "GATEWAY_TOKEN" not in page.text
    assert missing.status_code == 401
    assert wrong.status_code == 401


def test_frontend_never_auto_checks_patient_confirmation() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "services/web_demo/static/app.js"
    ).read_text(encoding="utf-8")

    assert "checkbox.checked = true" not in script
    assert "GATEWAY_TOKEN" not in script
    assert "recordingAutoStopStarted" in script
    assert "RECORDING_STOP_HEADROOM_SECONDS = 0.5" in script
    assert (
        "appState.maxAudioSeconds - RECORDING_STOP_HEADROOM_SECONDS"
        in script
    )


def test_frontend_uses_patient_facing_bilingual_explanations() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "services/web_demo/static/app.js"
    ).read_text(encoding="utf-8")

    assert 'sourceL2: "AI-assisted completion"' in script
    assert 'sourceL2: "AI 辅助补全"' in script
    assert 'riskOrdinary: "Standard confirmation"' in script
    assert 'riskOrdinary: "标准确认"' in script
    assert "candidateLabelsOverview" in script
    assert "final-details-explanation" in script
    assert "confirmationMethodLabel(receipt.confirmation_method)" in script
    assert "authorizationScopeLabel(receipt.authorization_scope)" in script
    assert "focus({ preventScroll: true })" in script


def test_frontend_has_a_branded_reduced_motion_launch_transition() -> None:
    root = Path(__file__).resolve().parents[2]
    markup = (root / "services/web_demo/static/index.html").read_text(
        encoding="utf-8",
    )
    styles = (root / "services/web_demo/static/styles.css").read_text(
        encoding="utf-8",
    )
    script = (root / "services/web_demo/static/app.js").read_text(
        encoding="utf-8",
    )

    assert 'id="launch-screen"' in markup
    assert "/assets/brand/logo-lockup-en.png" in markup
    assert 'id="brand-mark" class="brand-mark"' in markup
    assert 'src="/assets/brand/logo-mark.svg"' in markup
    assert "@keyframes launch-screen-out" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles
    assert "setupLaunchScreen()" in script
    assert "logo-lockup-${language}${darkSuffix}.png" in script


def test_frontend_supports_system_and_manual_dark_appearance() -> None:
    root = Path(__file__).resolve().parents[2]
    markup = (root / "services/web_demo/static/index.html").read_text(
        encoding="utf-8",
    )
    styles = (root / "services/web_demo/static/styles.css").read_text(
        encoding="utf-8",
    )
    script = (root / "services/web_demo/static/app.js").read_text(
        encoding="utf-8",
    )

    assert 'content="light dark"' in markup
    assert 'id="appearance-select"' in markup
    assert 'value="auto"' in markup
    assert 'value="light"' in markup
    assert 'value="dark"' in markup
    assert "@media (prefers-color-scheme: dark)" in styles
    assert ':root[data-theme="dark"]' in styles
    assert "systemDarkAppearance" in script
    assert "meantbyme_ui_appearance" in script
    assert "/assets/brand/logo-mark${darkSuffix}.svg" in script
    assert "logo-lockup-${language}${darkSuffix}.png" in script


def test_desktop_frontend_expands_into_a_web_workspace() -> None:
    root = Path(__file__).resolve().parents[2]
    markup = (root / "services/web_demo/static/index.html").read_text(
        encoding="utf-8",
    )
    styles = (root / "services/web_demo/static/styles.css").read_text(
        encoding="utf-8",
    )

    assert "styles.css?v=ios-web-1" in markup
    assert "app.js?v=ios-web-1" in markup
    assert "a native web inspector from 900px" in markup
    assert "max-width: 100rem" in styles
    assert "flex: 1 1 auto" in styles
    assert "max-width: 52rem" in styles
    assert "border-left: 1px solid var(--line)" in styles
    assert "flex-basis: 24.5625rem" not in styles
    assert "border-radius: 2.875rem" not in styles


def test_busy_state_never_re_enables_a_stage_disabled_control() -> None:
    """Releasing the busy state must not unlock "Confirm and speak".

    A blanket ``element.disabled = false`` sweep after a command completes
    re-enables the freshly rendered final-confirm button, which the final
    review stage renders disabled until the patient checks the private
    readback boxes. Only controls the busy sweep itself disabled may be
    restored, so the marker has to be read back before clearing.
    """
    script = (
        Path(__file__).resolve().parents[2]
        / "services/web_demo/static/app.js"
    ).read_text(encoding="utf-8")

    assert 'element.dataset.busyDisabled = "true"' in script
    assert 'element.dataset.busyDisabled === "true"' in script
    # The old unconditional sweep must not come back.
    assert "element.disabled = disabled" not in script


def test_profiles_are_protected_and_no_profile_is_a_memory_free_control(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        missing = client.get("/api/profiles")
        listed = client.get(
            "/api/profiles", headers={"X-Demo-Token": DEMO_TOKEN}
        )
        created = client.post(
            "/api/sessions",
            headers={"X-Demo-Token": DEMO_TOKEN},
            json={"language": "en"},
        )

    assert missing.status_code == 401
    assert [item["profile_ref"] for item in listed.json()["profiles"]] == [
        "no_profile",
        "lin_yue_demo",
        "david_demo",
    ]
    assert created.status_code == 200
    assert created.json()["profile"] == {
        "profile_id": "no_profile",
        "label": "No profile (control)",
        "semantic_count": 0,
        "context_count": 0,
        "skipped_count": 0,
    }


def test_structured_markdown_profile_upload_is_process_local_and_selectable(
    tmp_path: Path,
) -> None:
    profile = (
        Path(__file__).resolve().parents[2]
        / "demo/profiles/lin_yue_demo.md"
    ).read_bytes()
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        uploaded = client.post(
            "/api/profiles",
            headers={
                "X-Demo-Token": DEMO_TOKEN,
                "Content-Type": "text/markdown",
            },
            content=profile,
        )
        profile_ref = uploaded.json()["profile"]["profile_ref"]
        created = client.post(
            "/api/sessions",
            headers={"X-Demo-Token": DEMO_TOKEN},
            json={"language": "en", "profile_ref": profile_ref},
        )
        invalid = client.post(
            "/api/profiles",
            headers={
                "X-Demo-Token": DEMO_TOKEN,
                "Content-Type": "text/markdown",
            },
            content=b"# Unstructured personal narrative",
        )

    assert uploaded.status_code == 200
    assert uploaded.json()["profile"]["source"] == "uploaded"
    assert created.status_code == 200
    assert created.json()["profile"]["profile_id"] == "lin_yue_demo"
    assert created.json()["profile"]["context_count"] == 17
    assert created.json()["profile"]["skipped_count"] == 2
    assert invalid.status_code == 422


def test_audio_upload_accepts_limit_and_rejects_longer_wav(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        created, headers = _create_session(client)
        session_id = created["session"]["session_id"]
        exact_limit = client.post(
            f"/api/sessions/{session_id}/audio",
            headers={**headers, "Content-Type": "audio/wav"},
            content=wav_bytes(duration_seconds=20.0),
        )
        over_limit = client.post(
            f"/api/sessions/{session_id}/audio",
            headers={**headers, "Content-Type": "audio/wav"},
            content=wav_bytes(duration_seconds=20.01),
        )

    assert exact_limit.status_code == 200
    assert over_limit.status_code == 413
    assert over_limit.json()["detail"] == (
        "audio must be 20 seconds or shorter"
    )


def test_cloud_mode_fails_closed_without_demo_token(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path,
        mode="cloud",
        demo_token="",
        gateway_token="configured-but-never-called",
    )
    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/api/health").status_code == 200
        response = client.post("/api/sessions", json={"language": "en"})

    assert response.status_code == 503
    assert response.json()["detail"] == "demo token not configured"


def test_session_token_scopes_access_and_personal_audio_is_blocked(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        created, headers = _create_session(client)
        session_id = created["session"]["session_id"]
        wrong_headers = dict(headers)
        wrong_headers["X-Demo-Session"] = "another-session-token"

        cross_session = client.post(
            f"/api/sessions/{session_id}/commands",
            headers=wrong_headers,
            json={
                "command": "start_capture",
                "payload": {},
                "confirmation_method": None,
            },
        )
        personal = client.get(
            f"/api/sessions/{session_id}/audio/personal",
            headers=headers,
        )

    assert cross_session.status_code == 404
    assert personal.status_code == 404


def test_full_mock_browser_loop_completes_with_receipt_and_audio(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        created, headers = _create_session(client)
        session_id = created["session"]["session_id"]
        routed = _drive_to_candidates(client, session_id, headers)
        assert routed["session"]["heard_sequence"] == [
            {"text": "i", "status": "stable"},
            {"text": "don't", "status": "stable"},
            {"text": "want", "status": "uncertain"},
            {"text": "tomorrow", "status": "stable"},
        ]
        intended = next(
            candidate
            for candidate in routed["session"]["candidates"]
            if candidate["text"] == "I don't want to go tomorrow."
        )
        review = _command(
            client,
            session_id,
            headers,
            "select_candidate",
            payload={"candidate_id": intended["id"]},
        )
        assert review["session"]["stage"] == SessionStage.FINAL_REVIEW
        assert review["audio"]["neutral_available"] is True
        assert review["audio"]["personal_available"] is False
        neutral = client.get(
            f"/api/sessions/{session_id}/audio/neutral",
            headers=headers,
        )
        assert neutral.status_code == 200
        assert neutral.content.startswith(b"RIFF")

        completed = _command(
            client,
            session_id,
            headers,
            "final_confirm",
            payload={
                "private_readback_completed": True,
                "strict_confirmation": False,
            },
            confirmation_method="large_button",
        )
        personal = client.get(
            f"/api/sessions/{session_id}/audio/personal",
            headers=headers,
        )

    assert completed["session"]["stage"] == SessionStage.COMPLETED
    assert completed["receipt"]["patient_confirmed"] is True
    assert completed["audio"]["personal_available"] is True
    assert completed["session"]["personal_voice_status"] == "used"
    assert personal.status_code == 200
    assert personal.content.startswith(b"RIFF")
    event_types = [
        event["event_type"]
        for event in completed["session"]["trace_items"]
    ]
    assert event_types.index(
        RuntimeEventType.EXPRESSION_RECEIPT_CREATED
    ) < event_types.index(RuntimeEventType.VERIFIED_MEMORY_WRITTEN)
    assert event_types[-1] == RuntimeEventType.SESSION_COMPLETED


def test_client_cannot_supply_patient_identity(tmp_path: Path) -> None:
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        response = client.post(
            "/api/sessions",
            headers={"X-Demo-Token": DEMO_TOKEN},
            json={"language": "en", "patient_id": "other_patient"},
        )

    assert response.status_code == 422


def test_cloud_browser_loop_uses_stub_gateway_only(
    tmp_path: Path,
) -> None:
    state = StubGatewayState()
    with running_stub_gateway(state) as gateway:
        settings = _settings(
            tmp_path,
            mode="cloud",
            gateway_url=gateway.base_url,
            gateway_token="stub-gateway-token",
            gateway_timeout_seconds=1.0,
            gateway_max_attempts=1,
        )
        with TestClient(create_app(settings=settings)) as client:
            created, headers = _create_session(client)
            session_id = created["session"]["session_id"]
            upload = client.post(
                f"/api/sessions/{session_id}/audio",
                headers={
                    **headers,
                    "Content-Type": "audio/wav",
                },
                content=wav_bytes(),
            )
            assert upload.status_code == 200
            routed = _drive_to_candidates(client, session_id, headers)
            intended = next(
                candidate
                for candidate in routed["session"]["candidates"]
                if candidate["text"] == "I don't want to go tomorrow."
            )
            _command(
                client,
                session_id,
                headers,
                "select_candidate",
                payload={"candidate_id": intended["id"]},
            )
            completed = _command(
                client,
                session_id,
                headers,
                "final_confirm",
                payload={
                    "private_readback_completed": True,
                    "strict_confirmation": False,
                },
                confirmation_method="large_button",
            )

    assert completed["session"]["stage"] == SessionStage.COMPLETED
    assert completed["receipt"]["patient_confirmed"] is True
    assert state.last_intent_payload is not None
    assert state.last_intent_payload["situation"] is None
    context_event = next(
        event
        for event in completed["session"]["trace_items"]
        if event["event_type"] == RuntimeEventType.CONTEXT_RETRIEVED
    )
    assert context_event["payload"]["count"] == 0
