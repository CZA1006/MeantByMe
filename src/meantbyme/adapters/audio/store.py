from __future__ import annotations

import audioop
import io
import os
import re
import struct
import wave
from pathlib import Path


_AUDIO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_WAVE_FORMAT_PCM = 0x0001
_WAVE_FORMAT_EXTENSIBLE = 0xFFFE
_PCM_SUBFORMAT_GUID = bytes.fromhex(
    "0100000000001000800000aa00389b71"
)


class AudioStoreError(ValueError):
    pass


class AudioStore:
    """Local 16 kHz mono PCM WAV storage keyed by opaque audio_id."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        os.chmod(self._root, 0o700)

    def import_wav(
        self, source: str | Path, *, audio_id: str
    ) -> Path:
        return self.put_wav_bytes(audio_id, Path(source).read_bytes())

    def put_wav_bytes(self, audio_id: str, wav_bytes: bytes) -> Path:
        path = self.path_for(audio_id)
        normalized = self._normalize_wav(wav_bytes)
        path.write_bytes(normalized)
        os.chmod(path, 0o600)
        return path

    def capture_microphone(
        self,
        audio_id: str,
        *,
        duration_seconds: float,
        device: str | int | None = None,
    ) -> Path:
        if duration_seconds <= 0:
            raise AudioStoreError("duration_seconds must be positive")
        try:
            import sounddevice
        except ImportError as error:
            raise AudioStoreError(
                "Microphone capture requires the sounddevice package"
            ) from error

        frame_count = int(16_000 * duration_seconds)
        try:
            with sounddevice.RawInputStream(
                samplerate=16_000,
                channels=1,
                dtype="int16",
                device=device,
            ) as stream:
                frames, overflowed = stream.read(frame_count)
        except Exception as error:
            raise AudioStoreError(
                f"Microphone capture failed: {type(error).__name__}"
            ) from error
        if overflowed:
            raise AudioStoreError("Microphone capture overflowed")
        return self.put_wav_bytes(
            audio_id, self._encode_wav(bytes(frames), sample_rate=16_000)
        )

    def read_wav(self, audio_id: str) -> bytes:
        path = self.path_for(audio_id)
        if not path.is_file():
            raise AudioStoreError(f"Unknown audio_id: {audio_id}")
        data = path.read_bytes()
        self._inspect_wav(data)
        return data

    def delete(self, audio_id: str) -> None:
        path = self.path_for(audio_id)
        if path.exists():
            path.unlink()

    @classmethod
    def duration_seconds(cls, wav_bytes: bytes) -> float:
        channels, sample_width, sample_rate, frames = cls._inspect_wav(
            wav_bytes
        )
        bytes_per_frame = channels * sample_width
        if sample_rate <= 0 or bytes_per_frame <= 0:
            raise AudioStoreError("Invalid WAV format")
        return len(frames) / bytes_per_frame / sample_rate

    def path_for(self, audio_id: str) -> Path:
        if not _AUDIO_ID.fullmatch(audio_id):
            raise AudioStoreError("audio_id contains unsupported characters")
        return self._root / f"{audio_id}.wav"

    @classmethod
    def _normalize_wav(cls, wav_bytes: bytes) -> bytes:
        channels, sample_width, sample_rate, frames = cls._inspect_wav(
            wav_bytes
        )
        if channels == 2:
            frames = audioop.tomono(frames, sample_width, 0.5, 0.5)
        elif channels != 1:
            raise AudioStoreError("Only mono or stereo WAV input is supported")
        if sample_width == 1:
            frames = audioop.bias(frames, 1, -128)
        if sample_width != 2:
            frames = audioop.lin2lin(frames, sample_width, 2)
        if sample_rate != 16_000:
            frames, _ = audioop.ratecv(
                frames, 2, 1, sample_rate, 16_000, None
            )
        return cls._encode_wav(frames, sample_rate=16_000)

    @staticmethod
    def _inspect_wav(wav_bytes: bytes) -> tuple[int, int, int, bytes]:
        readable_wav = AudioStore._canonicalize_extensible_pcm(wav_bytes)
        try:
            with wave.open(io.BytesIO(readable_wav), "rb") as reader:
                if reader.getcomptype() != "NONE":
                    raise AudioStoreError("Compressed WAV input is unsupported")
                channels = reader.getnchannels()
                sample_width = reader.getsampwidth()
                sample_rate = reader.getframerate()
                frames = reader.readframes(reader.getnframes())
        except (EOFError, wave.Error) as error:
            raise AudioStoreError("Invalid WAV data") from error
        if sample_width not in {1, 2, 3, 4}:
            raise AudioStoreError("Unsupported PCM sample width")
        return channels, sample_width, sample_rate, frames

    @staticmethod
    def _canonicalize_extensible_pcm(wav_bytes: bytes) -> bytes:
        if (
            len(wav_bytes) < 12
            or wav_bytes[:4] != b"RIFF"
            or wav_bytes[8:12] != b"WAVE"
        ):
            return wav_bytes

        offset = 12
        while offset + 8 <= len(wav_bytes):
            chunk_id = wav_bytes[offset : offset + 4]
            chunk_size = struct.unpack_from("<I", wav_bytes, offset + 4)[0]
            chunk_start = offset + 8
            chunk_end = chunk_start + chunk_size
            if chunk_end > len(wav_bytes):
                raise AudioStoreError("Invalid WAV data")
            if chunk_id == b"fmt ":
                if chunk_size < 16:
                    raise AudioStoreError("Invalid WAV format")
                format_tag = struct.unpack_from(
                    "<H", wav_bytes, chunk_start
                )[0]
                if format_tag != _WAVE_FORMAT_EXTENSIBLE:
                    return wav_bytes
                if chunk_size < 40:
                    raise AudioStoreError("Invalid extensible WAV format")
                extension_size = struct.unpack_from(
                    "<H", wav_bytes, chunk_start + 16
                )[0]
                subformat = wav_bytes[
                    chunk_start + 24 : chunk_start + 40
                ]
                if (
                    extension_size < 22
                    or subformat != _PCM_SUBFORMAT_GUID
                ):
                    raise AudioStoreError(
                        "Only PCM extensible WAV input is supported"
                    )
                canonical = bytearray(wav_bytes)
                struct.pack_into(
                    "<H", canonical, chunk_start, _WAVE_FORMAT_PCM
                )
                return bytes(canonical)
            offset = chunk_end + (chunk_size % 2)
        return wav_bytes

    @staticmethod
    def _encode_wav(frames: bytes, *, sample_rate: int) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(sample_rate)
            writer.writeframes(frames)
        return output.getvalue()
