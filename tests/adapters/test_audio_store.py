from __future__ import annotations

import struct
import wave

import pytest

from meantbyme.adapters.audio import AudioStore, AudioStoreError


PCM_SUBFORMAT_GUID = bytes.fromhex(
    "0100000000001000800000aa00389b71"
)


def _extensible_pcm_wav(
    *,
    duration_seconds: float = 0.25,
    sample_rate: int = 48_000,
    subformat: bytes = PCM_SUBFORMAT_GUID,
) -> bytes:
    channels = 1
    sample_width = 2
    frame_count = int(duration_seconds * sample_rate)
    frames = b"\x01\x00" * frame_count
    block_align = channels * sample_width
    fmt = (
        struct.pack(
            "<HHIIHHH",
            0xFFFE,
            channels,
            sample_rate,
            sample_rate * block_align,
            block_align,
            sample_width * 8,
            22,
        )
        + struct.pack("<HI", sample_width * 8, 0x4)
        + subformat
    )
    chunks = (
        b"fmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"data"
        + struct.pack("<I", len(frames))
        + frames
    )
    return b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WAVE" + chunks


def test_extensible_pcm_wav_is_normalized_to_standard_16k_pcm(
    tmp_path,
) -> None:
    store = AudioStore(tmp_path / "audio")
    source = _extensible_pcm_wav()

    path = store.put_wav_bytes("extensible", source)

    with wave.open(str(path), "rb") as reader:
        assert reader.getcomptype() == "NONE"
        assert reader.getnchannels() == 1
        assert reader.getsampwidth() == 2
        assert reader.getframerate() == 16_000
        assert reader.getnframes() == 4_000


def test_extensible_pcm_duration_is_available_before_normalization() -> None:
    source = _extensible_pcm_wav(duration_seconds=0.25)

    assert AudioStore.duration_seconds(source) == pytest.approx(0.25)


def test_extensible_non_pcm_subformat_is_rejected() -> None:
    ieee_float_subformat = bytes.fromhex(
        "0300000000001000800000aa00389b71"
    )

    with pytest.raises(
        AudioStoreError,
        match="Only PCM extensible WAV input is supported",
    ):
        AudioStore.duration_seconds(
            _extensible_pcm_wav(subformat=ieee_float_subformat)
        )
