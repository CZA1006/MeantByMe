from __future__ import annotations

import pytest

from conftest import AUDIO_ID, PATIENT_ID, make_harness
from meantbyme.cli import CandidateCoverageMiss, _drive_golden_path
from meantbyme.core.domain import SessionStage


def test_cli_uses_none_of_these_instead_of_confirming_first_candidate() -> None:
    harness = make_harness(with_memory=False)

    with pytest.raises(CandidateCoverageMiss):
        _drive_golden_path(
            harness.runtime,
            audio_id=AUDIO_ID,
            intended_expression="This expression is not a candidate.",
        )

    session = harness.runtime.session
    assert session.stage is SessionStage.CANDIDATE_SELECTION
    assert session.selected_candidate_id is None
    assert session.patient_confirmed is False
    assert session.voice_authorized is False
    assert harness.tts.personal_calls == 0
    assert harness.repository.count_rejections(PATIENT_ID) == 3
    assert harness.repository.count_memory_writes(PATIENT_ID) == 0
