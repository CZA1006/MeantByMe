from meantbyme.adapters.asr import HeadsetPrimaryASRAdapter
from meantbyme.core.domain import ASRResult


class StubASR:
    def transcribe(self, audio_id: str) -> list[ASRResult]:
        return [
            ASRResult(
                provider="server_asr",
                transcript=f"server:{audio_id}",
                language="zh",
                status="success",
            )
        ]


def test_headset_primary_is_first_and_consumed_once() -> None:
    adapter = HeadsetPrimaryASRAdapter(StubASR())
    adapter.submit_primary("audio-1", "  我想喝水  ", language="zh")

    first = adapter.transcribe("audio-1")
    retry = adapter.transcribe("audio-1")

    assert [item.provider for item in first] == [
        "viaim_ios_primary",
        "server_asr",
    ]
    assert first[0].transcript == "我想喝水"
    assert [item.provider for item in retry] == ["server_asr"]
