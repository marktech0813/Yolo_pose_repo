"""Pause, repeat, and speaking-rate metrics."""

from __future__ import annotations

from dataclasses import dataclass, field

from app import config
from app.asr.transcriber import WordTiming
from app.fluency.fillers import is_filler_token


@dataclass
class PauseHit:
    start: float
    end: float
    duration: float


@dataclass
class RepeatHit:
    word: str
    start: float
    end: float


@dataclass
class FluencyMetrics:
    wpm: float | None = None
    speech_seconds: float | None = None
    pauses: list[PauseHit] = field(default_factory=list)
    repeats: list[RepeatHit] = field(default_factory=list)


def compute_fluency(words: list[WordTiming]) -> FluencyMetrics:
    if not words:
        return FluencyMetrics()

    pauses: list[PauseHit] = []
    for prev, cur in zip(words, words[1:]):
        gap = cur.start - prev.end
        if gap >= config.PAUSE_SECONDS:
            pauses.append(PauseHit(start=prev.end, end=cur.start, duration=gap))

    repeats: list[RepeatHit] = []
    for prev, cur in zip(words, words[1:]):
        a = prev.word.strip(".,!?;:\"' ").lower()
        b = cur.word.strip(".,!?;:\"' ").lower()
        if not a or a != b:
            continue
        if is_filler_token(a):
            continue
        repeats.append(RepeatHit(word=cur.word.strip(), start=prev.start, end=cur.end))

    first = words[0].start
    last = words[-1].end
    speech_seconds = max(0.0, last - first)
    content_count = sum(
        1
        for w in words
        if w.word.strip() and not is_filler_token(w.word.strip(".,!?;:\"' ").lower())
    )
    wpm = None
    if speech_seconds >= config.MIN_SPEECH_SECONDS_FOR_RATE and speech_seconds > 0:
        wpm = (content_count / speech_seconds) * 60.0

    return FluencyMetrics(
        wpm=wpm,
        speech_seconds=speech_seconds,
        pauses=pauses,
        repeats=repeats,
    )
