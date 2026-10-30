"""PCM 16-bit mono 16 kHz WAV validation and loading."""

from __future__ import annotations

import struct
import wave
from dataclasses import dataclass
from io import BytesIO

from app import config


class WavError(ValueError):
    """Invalid or unsupported WAV input."""


@dataclass(frozen=True)
class WavAudio:
    samples: list[float]
    sample_rate: int
    duration_sec: float


def _read_pcm16_mono(data: bytes) -> tuple[list[int], int, int]:
    try:
        with wave.open(BytesIO(data), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
    except wave.Error as exc:
        raise WavError(f"Invalid WAV file: {exc}") from exc

    if channels != 1:
        raise WavError("WAV must be mono (1 channel)")
    if sample_width != 2:
        raise WavError("WAV must be 16-bit PCM")
    if sample_rate != config.SAMPLE_RATE:
        raise WavError(f"WAV must be {config.SAMPLE_RATE} Hz (got {sample_rate})")

    frame_count = len(raw) // 2
    samples = list(struct.unpack(f"<{frame_count}h", raw[: frame_count * 2]))
    return samples, sample_rate, frame_count


def parse_wav(data: bytes) -> WavAudio:
    if len(data) > config.MAX_BODY_BYTES:
        raise WavError("Audio exceeds size limit")

    int_samples, sample_rate, frame_count = _read_pcm16_mono(data)
    duration = frame_count / float(sample_rate)

    if duration < config.MIN_AUDIO_SECONDS:
        raise WavError(
            f"Audio too short (min {config.MIN_AUDIO_SECONDS}s, got {duration:.2f}s)"
        )
    if duration > config.MAX_AUDIO_SECONDS:
        raise WavError(
            f"Audio too long (max {config.MAX_AUDIO_SECONDS}s, got {duration:.2f}s)"
        )

    floats = [s / 32768.0 for s in int_samples]
    return WavAudio(samples=floats, sample_rate=sample_rate, duration_sec=duration)


def write_silence_wav(path, duration_sec: float = 1.0, sample_rate: int = config.SAMPLE_RATE) -> None:
    """Write a short silent mono WAV (for fixtures)."""
    n_frames = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)
