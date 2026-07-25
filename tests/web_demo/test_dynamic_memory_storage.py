from pathlib import Path

from services.web_demo.profile_storage import SQLiteProfileStore


def _record(
    store: SQLiteProfileStore,
    *,
    session_id: str,
    confirmed: bool,
    profile_ref: str = "david_demo",
):
    return store.record_expression_feedback(
        profile_ref=profile_ref,
        profile_id="patient-david-demo",
        session_id=session_id,
        input_text="blue cup please",
        intent_text="I would like the blue cup.",
        language="en",
        confirmed=confirmed,
    )


def test_confirm_and_reject_update_the_same_mapping(tmp_path: Path) -> None:
    store = SQLiteProfileStore(tmp_path / "profiles.sqlite3")

    first = _record(store, session_id="session-1", confirmed=True)
    repeated = _record(store, session_id="session-2", confirmed=True)
    rejected = _record(store, session_id="session-3", confirmed=False)

    assert first.confidence == 0.65
    assert repeated.confidence == 0.75
    assert repeated.positive_count == 2
    assert rejected.confidence == 0.55
    assert rejected.negative_count == 1
    store.close()


def test_feedback_retry_is_idempotent(tmp_path: Path) -> None:
    store = SQLiteProfileStore(tmp_path / "profiles.sqlite3")

    first = _record(store, session_id="session-1", confirmed=True)
    retried = _record(store, session_id="session-1", confirmed=True)

    assert retried.mapping_id == first.mapping_id
    assert retried.confidence == first.confidence
    assert retried.positive_count == 1
    store.close()


def test_negative_only_mapping_is_stored_but_not_retrievable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "profiles.sqlite3"
    store = SQLiteProfileStore(path)
    negative = _record(store, session_id="session-1", confirmed=False)

    assert negative.confidence == 0.35
    assert store.list_expression_mappings(
        profile_ref="david_demo",
        profile_id="patient-david-demo",
        min_confidence=0.55,
    ) == []
    store.close()

    reopened = SQLiteProfileStore(path)
    all_mappings = reopened.list_expression_mappings(
        profile_ref="david_demo",
        profile_id="patient-david-demo",
    )
    assert len(all_mappings) == 1
    assert all_mappings[0].negative_count == 1
    reopened.close()


def test_expression_mappings_are_profile_scoped(tmp_path: Path) -> None:
    store = SQLiteProfileStore(tmp_path / "profiles.sqlite3")
    _record(store, session_id="session-1", confirmed=True)
    other = _record(
        store,
        session_id="session-2",
        confirmed=True,
        profile_ref="another_profile",
    )

    other_profile = store.list_expression_mappings(
        profile_ref="another_profile",
        profile_id="patient-david-demo",
    )
    assert [mapping.mapping_id for mapping in other_profile] == [
        other.mapping_id
    ]
    assert store.list_expression_mappings(
        profile_ref="david_demo",
        profile_id="another_patient",
    ) == []
    assert other.mapping_id != store.list_expression_mappings(
        profile_ref="david_demo",
        profile_id="patient-david-demo",
    )[0].mapping_id
    store.close()
