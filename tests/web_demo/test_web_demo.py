from __future__ import annotations

import base64
import json
from pathlib import Path

from fastapi.testclient import TestClient

from meantbyme.core.domain import RuntimeEventType, SessionStage
from services.web_demo.app import create_app
from services.web_demo.config import WebDemoSettings
from services.web_demo.scripted_demo import LIN_YUE_SCRIPTED_TEXT
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


def _create_qa_session(
    client: TestClient,
) -> tuple[dict, dict[str, str]]:
    response = client.post(
        "/api/qa/sessions",
        headers={"X-Demo-Token": DEMO_TOKEN},
        json={"language": "en", "profile_ref": "david_demo"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload, {
        "X-Demo-Token": DEMO_TOKEN,
        "X-Demo-Session": payload["session_token"],
    }


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
    assert health.json()["profile_database_backend"] == "sqlite"
    assert DEMO_TOKEN not in health.text
    assert page.status_code == 200
    assert "GATEWAY_TOKEN" not in page.text
    assert missing.status_code == 401
    assert wrong.status_code == 401


def test_qa_session_answers_without_confirmation_and_can_cancel_turn(
    tmp_path: Path,
) -> None:
    transcript_header = base64.b64encode(
        b"why is the sky blue"
    ).decode("ascii")
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        created, headers = _create_qa_session(client)
        session_id = created["session_id"]
        turn_id = "turn-1"
        answered = client.post(
            f"/api/qa/sessions/{session_id}/turns/{turn_id}",
            headers={
                **headers,
                "Content-Type": "audio/wav",
                "X-Viaim-Primary-Transcript-B64": transcript_header,
            },
            content=wav_bytes(),
        )
        audio = client.get(
            f"/api/qa/sessions/{session_id}/turns/{turn_id}/audio",
            headers=headers,
        )
        cancelled = client.post(
            (
                f"/api/qa/sessions/{session_id}/turns/"
                f"{turn_id}/cancel"
            ),
            headers=headers,
        )
        missing_audio = client.get(
            f"/api/qa/sessions/{session_id}/turns/{turn_id}/audio",
            headers=headers,
        )
        stopped = client.post(
            f"/api/qa/sessions/{session_id}/stop", headers=headers
        )

    assert answered.status_code == 200, answered.text
    payload = answered.json()
    assert payload["response"]["should_clarify"] is False
    assert payload["audio_available"] is True
    assert payload["voice_mode"] == "neutral_private_only"
    assert payload["memory_write_enabled"] is False
    assert "receipt" not in payload
    assert audio.status_code == 200
    assert audio.content.startswith(b"RIFF")
    assert cancelled.status_code == 200
    assert cancelled.json()["turn_count"] == 0
    assert cancelled.json()["removed_from_context"] is True
    assert missing_audio.status_code == 404
    assert stopped.status_code == 200
    assert stopped.json()["stopped"] is True


def test_expression_upload_merges_viaim_primary_without_echoing_text(
    tmp_path: Path,
) -> None:
    transcript = "I don't tomorrow"
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        created, headers = _create_session(client)
        session_id = created["session"]["session_id"]
        upload = client.post(
            f"/api/sessions/{session_id}/audio",
            headers={
                **headers,
                "Content-Type": "audio/wav",
                "X-Viaim-Primary-Transcript-B64": base64.b64encode(
                    transcript.encode("utf-8")
                ).decode("ascii"),
            },
            content=wav_bytes(),
        )
        _command(client, session_id, headers, "start_capture")
        heard = _command(client, session_id, headers, "stop_capture")

    assert upload.status_code == 200
    assert transcript not in upload.text
    asr_events = [
        event
        for event in heard["session"]["trace_items"]
        if event["event_type"] == RuntimeEventType.ASR_RESULT_RECEIVED
    ]
    assert asr_events[0]["payload"]["provider"] == "viaim_ios_primary"
    assert transcript not in str(asr_events)


def test_lin_yue_demo_is_scripted_without_gateway_models(
    tmp_path: Path,
) -> None:
    settings = _settings(
        tmp_path,
        mode="cloud",
        gateway_token="",
        lin_yue_scripted_demo_delay_seconds=0,
    )
    with TestClient(create_app(settings=settings)) as client:
        created_response = client.post(
            "/api/sessions",
            headers={"X-Demo-Token": DEMO_TOKEN},
            json={"language": "en", "profile_ref": "lin_yue_demo"},
        )
        assert created_response.status_code == 200
        created = created_response.json()
        session_id = created["session"]["session_id"]
        headers = {
            "X-Demo-Token": DEMO_TOKEN,
            "X-Demo-Session": created["session_token"],
        }
        _command(client, session_id, headers, "start_capture")
        upload = client.post(
            f"/api/sessions/{session_id}/audio",
            headers={
                **headers,
                "Content-Type": "audio/wav",
                "X-Viaim-Primary-Transcript-B64": base64.b64encode(
                    b"this live transcript must be ignored"
                ).decode("ascii"),
            },
            content=wav_bytes(),
        )
        heard = _command(client, session_id, headers, "stop_capture")
        candidates = _command(
            client,
            session_id,
            headers,
            "proceed_without_heard_confirmation",
        )
        prepared = _command(
            client,
            session_id,
            headers,
            "prepare_candidate_readback",
            payload={
                "candidate_id": candidates["session"]["candidates"][0]["id"]
            },
        )

    assert upload.status_code == 200
    assert "this live transcript must be ignored" not in [
        *heard["session"]["heard_stable"],
        *heard["session"]["heard_uncertain"],
    ]
    assert candidates["session"]["candidates"][0]["text"] == (
        LIN_YUE_SCRIPTED_TEXT
    )
    assert prepared["session"]["stage"] == SessionStage.FINAL_REVIEW
    asr_providers = [
        event["payload"]["provider"]
        for event in heard["session"]["trace_items"]
        if event["event_type"] == RuntimeEventType.ASR_RESULT_RECEIVED
    ]
    assert asr_providers == [
        "lin_yue_demo_primary",
        "lin_yue_demo_secondary",
    ]


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
    assert "Remember this" not in script
    assert "profile-updates" not in script


def test_cancel_expression_is_distinct_from_stopping_companion(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        created, headers = _create_session(client)
        session_id = created["session"]["session_id"]
        _command(client, session_id, headers, "start_capture")
        cancelled = _command(
            client,
            session_id,
            headers,
            "cancel_expression",
        )

    assert (
        cancelled["session"]["stage"]
        == SessionStage.EXPRESSION_CANCELLED
    )
    assert cancelled["session"]["candidates"] == []
    assert cancelled["receipt"] is None
    event = next(
        item
        for item in cancelled["session"]["trace_items"]
        if item["event_type"] == RuntimeEventType.EXPRESSION_CANCELLED
    )
    assert event["payload"]["actor"] == "caregiver"
    assert all(
        item["event_type"] != RuntimeEventType.SESSION_STOPPED
        for item in cancelled["session"]["trace_items"]
    )


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


def test_structured_markdown_profile_upload_is_persistent_and_selectable(
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
    assert created.json()["profile"]["context_count"] == 6
    assert created.json()["profile"]["skipped_count"] == 1
    assert invalid.status_code == 422


def test_questionnaire_profile_is_trusted_persistent_and_selectable(
    tmp_path: Path,
) -> None:
    settings = _settings(
        tmp_path,
        profile_database_path=tmp_path / "profiles.sqlite3",
    )
    with TestClient(create_app(settings=settings)) as client:
        created_profile = client.post(
            "/api/profiles/questionnaire",
            headers={"X-Demo-Token": DEMO_TOKEN},
            json={
                "display_name": "王奶奶",
                "language": "en",
                "background": "住在杭州，退休前是教师。",
                "relationships": "女儿叫小雨。",
                "communication_preferences": "希望别人一次只问一个问题。",
            },
        )
        assert created_profile.status_code == 200
        summary = created_profile.json()["profile"]
        profile_ref = summary["profile_ref"]
        detail = client.get(
            f"/api/profiles/{profile_ref}",
            headers={"X-Demo-Token": DEMO_TOKEN},
        )
        session = client.post(
            "/api/sessions",
            headers={"X-Demo-Token": DEMO_TOKEN},
            json={"language": "en", "profile_ref": profile_ref},
        )

    assert summary["label"] == "王奶奶"
    assert summary["source"] == "questionnaire"
    assert summary["simulated"] is False
    assert summary["memory_count"] == 3
    assert detail.status_code == 200
    memories = detail.json()["profile"]["memories"]
    assert all(item["source"] == "user_input" for item in memories)
    assert all(item["trust_state"] == "trusted" for item in memories)
    assert session.status_code == 200
    assert session.json()["profile"]["profile_id"].startswith("user-")
    assert session.json()["profile"]["context_count"] == 3

    # A new app process using the same server database can still resolve it.
    with TestClient(create_app(settings=settings)) as restarted:
        listed = restarted.get(
            "/api/profiles",
            headers={"X-Demo-Token": DEMO_TOKEN},
        )
        persisted_refs = {
            item["profile_ref"]
            for item in listed.json()["profiles"]
        }
        persisted_detail = restarted.get(
            f"/api/profiles/{profile_ref}",
            headers={"X-Demo-Token": DEMO_TOKEN},
        )

    assert profile_ref in persisted_refs
    assert persisted_detail.status_code == 200
    assert persisted_detail.json()["profile"]["display_name"] == "王奶奶"


def test_questionnaire_requires_profile_content(tmp_path: Path) -> None:
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        response = client.post(
            "/api/profiles/questionnaire",
            headers={"X-Demo-Token": DEMO_TOKEN},
            json={"display_name": "空档案", "language": "zh"},
        )

    assert response.status_code == 422


def test_explicit_markdown_import_is_trusted_without_voice_authority(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": 1,
        "simulated": False,
        "profile_id": "real-import",
        "label": "Imported user",
        "patient": {
            "patient_id": "real-import",
            "display_name": "Imported user",
            "languages": ["zh"],
            "default_language": "zh",
        },
        "consent": {
            "scope": "app_personalization",
            "cloud_processing_allowed": True,
        },
        "memories": [
            {
                "simulated": False,
                "id": "claimed-gold",
                "memory_type": "context",
                "verification_level": "gold",
                "source": "patient",
                "text": "文件声称这已经由患者确认。",
                "language": "zh",
                "context": {"kind": "personal_background"},
                "usage_count": 0,
                "confirmation_session_id": "self-asserted",
                "sensitivity": "ordinary",
                "prompt_eligible": True,
            }
        ],
    }
    markdown = (
        "# Imported\n\n```meantbyme-profile\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n```\n"
    )
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        uploaded = client.post(
            "/api/profiles",
            headers={
                "X-Demo-Token": DEMO_TOKEN,
                "Content-Type": "text/markdown",
            },
            content=markdown.encode("utf-8"),
        )
        profile_ref = uploaded.json()["profile"]["profile_ref"]
        detail = client.get(
            f"/api/profiles/{profile_ref}",
            headers={"X-Demo-Token": DEMO_TOKEN},
        )

    assert uploaded.status_code == 200
    memory = detail.json()["profile"]["memories"][0]
    assert memory["trust_state"] == "trusted"
    assert memory["source"] == "user_input"


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


def test_earbud_command_requires_two_matching_interpretations(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        created, headers = _create_session(client)
        session_id = created["session"]["session_id"]
        agreed = client.post(
            f"/api/sessions/{session_id}/earbud/interpret",
            headers={
                **headers,
                "Content-Type": "audio/wav",
                "X-Viaim-Primary-Transcript-B64": base64.b64encode(
                    b"yes"
                ).decode("ascii"),
                "X-MeantByMe-Prompt-ID": "prompt-agreed",
                "X-Mock-Secondary-Transcript-B64": base64.b64encode(
                    b"yes"
                ).decode("ascii"),
            },
            content=wav_bytes(duration_seconds=1),
        )
        disagreed = client.post(
            f"/api/sessions/{session_id}/earbud/interpret",
            headers={
                **headers,
                "Content-Type": "audio/wav",
                "X-Viaim-Primary-Transcript-B64": base64.b64encode(
                    b"yes"
                ).decode("ascii"),
                "X-MeantByMe-Prompt-ID": "prompt-disagreed",
                "X-Mock-Secondary-Transcript-B64": base64.b64encode(
                    b"no"
                ).decode("ascii"),
            },
            content=wav_bytes(duration_seconds=1),
        )

    assert agreed.status_code == 200
    assert agreed.json()["interpretation_id"].startswith(
        "voice-interpretation-"
    )
    assert agreed.json()["intent"] == "affirm"
    assert agreed.json()["consensus"] is True
    assert disagreed.status_code == 200
    assert disagreed.json()["intent"] == "unknown"
    assert disagreed.json()["consensus"] is False


def test_voice_confirmation_uses_server_issued_evidence_and_neutral_audio(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        created, headers = _create_session(client)
        session_id = created["session"]["session_id"]
        _command(client, session_id, headers, "start_capture")
        _command(client, session_id, headers, "stop_capture")
        candidates = _command(
            client,
            session_id,
            headers,
            "proceed_without_heard_confirmation",
        )
        candidate = candidates["session"]["candidates"][0]
        review = _command(
            client,
            session_id,
            headers,
            "prepare_candidate_readback",
            payload={"candidate_id": candidate["id"]},
        )
        assert review["session"]["stage"] == SessionStage.FINAL_REVIEW

        forged = client.post(
            f"/api/sessions/{session_id}/commands",
            headers=headers,
            json={
                "command": "confirm_neutral_playback",
                "confirmation_method": "voice_semantic",
                "payload": {
                    "private_readback_completed": True,
                    "voice_confirmation_evidence": {
                        "intent": "affirm",
                        "consensus": True,
                        "prompt_id": "forged",
                        "audio_hash": "forged",
                    },
                },
            },
        )
        assert forged.status_code == 409

        interpreted = client.post(
            f"/api/sessions/{session_id}/earbud/interpret",
            headers={
                **headers,
                "Content-Type": "audio/wav",
                "X-Viaim-Primary-Transcript-B64": base64.b64encode(
                    b"yes"
                ).decode("ascii"),
                "X-MeantByMe-Prompt-ID": "private-prompt-one",
                "X-Mock-Secondary-Transcript-B64": base64.b64encode(
                    b"yes"
                ).decode("ascii"),
            },
            content=wav_bytes(duration_seconds=1),
        )
        assert interpreted.status_code == 200
        confirmed = _command(
            client,
            session_id,
            headers,
            "confirm_neutral_playback",
            payload={
                "private_readback_completed": True,
                "voice_interpretation_ids": [
                    interpreted.json()["interpretation_id"]
                ],
            },
            confirmation_method="voice_semantic",
        )
        assert confirmed["session"]["stage"] == (
            SessionStage.PATIENT_CONFIRMED
        )
        assert confirmed["audio"]["personal_available"] is False

        completed = _command(
            client,
            session_id,
            headers,
            "playback_completed",
            payload={
                "playback_id": "neutral-voice-confirmed-001",
                "output_channel": "iphone_speaker",
            },
        )

    assert completed["session"]["stage"] == SessionStage.COMPLETED
    assert completed["receipt"]["confirmation_method"] == "voice_semantic"
    assert completed["receipt"]["voice_profile_id"] is None
    assert completed["receipt"]["authorization_scope"] is None


def test_large_button_confirmation_does_not_require_voice_evidence(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(settings=_settings(tmp_path))) as client:
        created, headers = _create_session(client)
        session_id = created["session"]["session_id"]
        _command(client, session_id, headers, "start_capture")
        _command(client, session_id, headers, "stop_capture")
        candidates = _command(
            client,
            session_id,
            headers,
            "proceed_without_heard_confirmation",
        )
        candidate = candidates["session"]["candidates"][0]
        _command(
            client,
            session_id,
            headers,
            "prepare_candidate_readback",
            payload={"candidate_id": candidate["id"]},
        )

        confirmed = _command(
            client,
            session_id,
            headers,
            "confirm_neutral_playback",
            payload={"private_readback_completed": True},
            confirmation_method="large_button",
        )
        completed = _command(
            client,
            session_id,
            headers,
            "playback_completed",
            payload={
                "playback_id": "neutral-button-confirmed-001",
                "output_channel": "iphone_speaker",
            },
        )

    assert confirmed["session"]["stage"] == SessionStage.PATIENT_CONFIRMED
    assert confirmed["dynamic_memory"]["feedback_status"] == (
        "positive_recorded"
    )
    assert confirmed["audio"]["personal_available"] is False
    assert completed["session"]["stage"] == SessionStage.COMPLETED
    assert completed["receipt"]["confirmation_method"] == "large_button"
    assert completed["receipt"]["voice_profile_id"] is None


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

        authorized = _command(
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
        profile_detail = client.get(
            "/api/profiles/david_demo",
            headers={"X-Demo-Token": DEMO_TOKEN},
        )
        personal = client.get(
            f"/api/sessions/{session_id}/audio/personal",
            headers=headers,
        )
        completed = _command(
            client,
            session_id,
            headers,
            "playback_completed",
            payload={
                "playback_id": "browser-playback-001",
                "output_channel": "browser_speaker",
            },
        )

    assert authorized["session"]["stage"] == SessionStage.VOICE_AUTHORIZED
    assert authorized["dynamic_memory"] == {
        "feedback_status": "positive_recorded",
        "requires_extra_confirmation": False,
    }
    assert (
        profile_detail.json()["profile"]["expression_mapping_count"] == 1
    )
    assert authorized["receipt"] is None
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
            authorized = _command(
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
            completed = _command(
                client,
                session_id,
                headers,
                "playback_completed",
                payload={
                    "playback_id": "browser-playback-cloud-001",
                    "output_channel": "browser_speaker",
                },
            )

    assert authorized["session"]["stage"] == SessionStage.VOICE_AUTHORIZED
    assert authorized["receipt"] is None
    assert completed["session"]["stage"] == SessionStage.COMPLETED
    assert completed["receipt"]["patient_confirmed"] is True
    assert state.last_intent_payload is not None
    model_context = state.last_intent_payload["situation"]
    assert "Current user profile" in model_context
    assert "Daughter Mia visits on weekends." in model_context
    assert "living-room window open" in model_context
    context_event = next(
        event
        for event in completed["session"]["trace_items"]
        if event["event_type"] == RuntimeEventType.CONTEXT_RETRIEVED
    )
    assert context_event["payload"]["count"] == 3


def test_cloud_qa_session_sends_temporary_multiturn_history(
    tmp_path: Path,
) -> None:
    state = StubGatewayState()
    transcript = "I don't want to go tomorrow"
    encoded = base64.b64encode(transcript.encode()).decode("ascii")
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
            created, headers = _create_qa_session(client)
            session_id = created["session_id"]
            for turn_id in ("turn-1", "turn-2"):
                answer = client.post(
                    (
                        f"/api/qa/sessions/{session_id}/turns/"
                        f"{turn_id}"
                    ),
                    headers={
                        **headers,
                        "Content-Type": "audio/wav",
                        "X-Viaim-Primary-Transcript-B64": encoded,
                    },
                    content=wav_bytes(),
                )
                assert answer.status_code == 200, answer.text
                assert answer.json()["response"]["answer"] == (
                    "This is the stub AI answer."
                )

    assert state.last_qa_payload is not None
    qa_model_context = state.last_qa_payload["situation"]
    assert "Current user profile" in qa_model_context
    assert "Daughter Mia visits on weekends." in qa_model_context
    assert [turn["role"] for turn in state.last_qa_payload["history"]] == [
        "user",
        "assistant",
    ]
