from pathlib import Path

import pytest

from app.audio.wav import WavError, parse_wav, write_silence_wav


def test_parse_valid_wav(tmp_path: Path):
    path = tmp_path / "ok.wav"
    write_silence_wav(path, duration_sec=1.0)
    data = path.read_bytes()
    audio = parse_wav(data)
    assert audio.sample_rate == 16000
    assert 0.9 < audio.duration_sec < 1.1
    assert len(audio.samples) == 16000


def test_reject_too_short(tmp_path: Path):
    path = tmp_path / "short.wav"
    write_silence_wav(path, duration_sec=0.1)
    with pytest.raises(WavError, match="too short"):
        parse_wav(path.read_bytes())


def test_reject_invalid():
    with pytest.raises(WavError):
        parse_wav(b"not a wav")
