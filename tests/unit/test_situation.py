from tests.conftest import make_harness


def test_situation_is_optional_and_settable_at_session_creation() -> None:
    without_situation = make_harness(session_id="situation-none")
    with_situation = make_harness(
        session_id="situation-present",
        situation="A friend asked about tomorrow's plan.",
    )

    assert without_situation.runtime.session.situation is None
    assert (
        with_situation.runtime.session.situation
        == "A friend asked about tomorrow's plan."
    )
