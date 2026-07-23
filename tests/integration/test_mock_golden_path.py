from meantbyme.cli import run_mock
from meantbyme.core.domain import RuntimeEventType, SessionStage


def test_full_mock_golden_path() -> None:
    result = run_mock()

    assert result["final_stage"] == SessionStage.COMPLETED.value
    assert result["unauthorized_voice_rate"] == 0
    assert result["receipt"]["patient_confirmed"] is True
    assert result["receipt"]["signature"] is None
    event_types = [item["event_type"] for item in result["trace"]]
    assert event_types.index(
        RuntimeEventType.EXPRESSION_RECEIPT_CREATED.value
    ) < event_types.index(RuntimeEventType.VERIFIED_MEMORY_WRITTEN.value)
    assert event_types[-1] == RuntimeEventType.SESSION_COMPLETED.value
