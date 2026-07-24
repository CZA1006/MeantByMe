from __future__ import annotations

import json
from pathlib import Path

import pytest

from meantbyme.adapters.profile import (
    ProfileBundleError,
    load_profile_bundle,
    parse_profile_markdown,
    seed_profile_repository,
)
from meantbyme.adapters.storage import SQLiteRepository
from meantbyme.core.domain import VerificationLevel
from meantbyme.core.personalization import expression_hash


ROOT = Path(__file__).resolve().parents[2]


def _document(payload: dict) -> str:
    return (
        "# Simulated profile\n\n```meantbyme-profile\n"
        + json.dumps(payload)
        + "\n```\n"
    )


def _valid_payload() -> dict:
    return {
        "schema_version": 1,
        "simulated": True,
        "profile_id": "profile-test",
        "label": "Profile test",
        "patient": {
            "patient_id": "profile-test",
            "display_name": "Test Patient",
            "languages": ["en"],
            "default_language": "en",
        },
        "consent": {
            "scope": "demo_testing",
            "cloud_processing_allowed": True,
        },
        "voice_consent": {
            "authorization_id": "voice-profile-test",
            "consent_session_id": "voice-session-test",
            "voice_profile_id": "official-voice",
        },
        "memories": [
            {
                "simulated": True,
                "id": "patient-context",
                "memory_type": "context",
                "verification_level": "gold",
                "source": "patient",
                "text": "Builds communication software.",
                "language": "en",
                "context": {"tags": ["software", "communication"]},
                "confirmation_session_id": "confirmed-profile-context",
                "sensitivity": "ordinary",
                "prompt_eligible": True,
            },
            {
                "simulated": True,
                "id": "research-note",
                "memory_type": "context",
                "verification_level": "unverified",
                "source": "research_fixture",
                "text": "An unverified research assumption.",
                "language": "en",
                "context": {},
                "confirmation_session_id": None,
                "sensitivity": "sensitive",
                "prompt_eligible": False,
            },
        ],
    }


def test_profile_bundle_requires_simulated_provenance_and_gold_confirmation() -> None:
    payload = _valid_payload()
    del payload["simulated"]
    with pytest.raises(ProfileBundleError, match="simulated"):
        parse_profile_markdown(_document(payload))

    payload = _valid_payload()
    payload["memories"][0]["confirmation_session_id"] = None
    with pytest.raises(ProfileBundleError, match="confirmation_session_id"):
        parse_profile_markdown(_document(payload))

    payload = _valid_payload()
    payload["memories"][0]["source"] = "caregiver"
    payload["memories"][0]["text"] = "PRIVATE PROFILE TEXT"
    with pytest.raises(
        ProfileBundleError, match="caregiver memory must be Silver"
    ) as error:
        parse_profile_markdown(_document(payload))
    assert "PRIVATE PROFILE TEXT" not in str(error.value)


def test_profile_import_seeds_only_verified_prompt_eligible_memory() -> None:
    profile = parse_profile_markdown(_document(_valid_payload()))
    repository = SQLiteRepository()

    result = seed_profile_repository(repository, profile)
    stored = repository.search_context_memories(profile.profile_id)

    assert result.context_count == 1
    assert result.semantic_count == 0
    assert result.skipped_memory_ids == ["research-note"]
    assert [memory.id for memory in stored] == ["patient-context"]
    assert stored[0].verification_level is VerificationLevel.GOLD
    assert stored[0].context["source"] == "patient"
    assert repository.has_active_voice_consent(
        profile.profile_id, "official-voice"
    )


def test_lin_yue_profile_selects_relevant_context_without_expected_answer() -> None:
    profile_path = ROOT / "demo/profiles/lin_yue_demo.md"
    source = profile_path.read_text(encoding="utf-8")
    profile = load_profile_bundle(profile_path)
    repository = SQLiteRepository()
    seed_profile_repository(repository, profile)

    selected = repository.search_context_memories(
        profile.profile_id,
        [
            "hi",
            "we",
            "help",
            "stroke",
            "survivors",
            "organize",
            "confirmation",
        ],
        limit=5,
    )

    assert selected
    assert "ctx-lin-yue-meantbyme-project" in {
        memory.id for memory in selected
    }
    assert all("treatment" not in (memory.text or "").casefold() for memory in selected)
    assert (
        "Hi, we are MeantByMe. We help stroke survivors organize their needs, "
        "and we speak only after confirmation."
        not in source
    )
    assert expression_hash("I don't want to go tomorrow.") == (
        "0410b0292a7e52d8b2d0c99717f2cc679e4de296be18e4372d9818e4908db17f"
    )
