"""Native-accent / pronunciation alerts from ASR word confidence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app import config
from app.asr.transcriber import WordTiming
from app.fluency.fillers import is_filler_token


@dataclass
class PronunciationAlert:
    word: str
    start: float
    end: float
    probability: float
    severity: str = "warn"  # warn | soft
    char_start: int | None = None
    char_length: int | None = None


_WORD_RE = re.compile(r"[A-Za-z']+")


def _normalize_token(token: str) -> str:
    m = _WORD_RE.search(token)
    return (m.group(0) if m else token).lower()


def find_pronunciation_alerts(words: list[WordTiming]) -> list[PronunciationAlert]:
    """Flag words that diverge from confident native-like recognition."""
    alerts: list[PronunciationAlert] = []
    for w in words:
        norm = _normalize_token(w.word)
        if len(norm) < config.MIN_PRONUNCIATION_WORD_LEN:
            continue
        if norm in config.FUNCTION_WORDS:
            continue
        if is_filler_token(norm):
            continue
        if w.probability < config.PRONUNCIATION_PROB_THRESHOLD:
            alerts.append(
                PronunciationAlert(
                    word=w.word.strip(),
                    start=w.start,
                    end=w.end,
                    probability=w.probability,
                    severity="warn",
                )
            )
        elif w.probability < config.ACCENT_SOFT_THRESHOLD:
            alerts.append(
                PronunciationAlert(
                    word=w.word.strip(),
                    start=w.start,
                    end=w.end,
                    probability=w.probability,
                    severity="soft",
                )
            )
    return alerts
