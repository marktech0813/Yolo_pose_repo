"""Closed-list filler detection."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.asr.transcriber import WordTiming

FILLER_WORDS = frozenset({"um", "uh", "er", "erm", "ah", "hmm", "mm"})
FILLER_PHRASES = (
    "you know",
    "i mean",
    "sort of",
    "kind of",
    "or something",
)


@dataclass
class FillerHit:
    text: str
    start: float | None
    end: float | None
    char_start: int | None = None
    char_length: int | None = None


def is_filler_token(token: str) -> bool:
    t = re.sub(r"[^a-z']", "", token.lower())
    return t in FILLER_WORDS


def _normalize_word(token: str) -> str:
    return re.sub(r"[^a-z']", "", token.lower())


def find_fillers_in_words(words: list[WordTiming]) -> list[FillerHit]:
    hits: list[FillerHit] = []
    norms = [_normalize_word(w.word) for w in words]
    i = 0
    while i < len(words):
        # phrases first (longest)
        matched = False
        for phrase in sorted(FILLER_PHRASES, key=len, reverse=True):
            parts = phrase.split()
            if i + len(parts) <= len(norms) and norms[i : i + len(parts)] == parts:
                hits.append(
                    FillerHit(
                        text=phrase,
                        start=words[i].start,
                        end=words[i + len(parts) - 1].end,
                    )
                )
                i += len(parts)
                matched = True
                break
        if matched:
            continue
        if norms[i] in FILLER_WORDS:
            hits.append(
                FillerHit(text=norms[i], start=words[i].start, end=words[i].end)
            )
        i += 1
    return hits


def find_fillers_in_text(text: str) -> list[FillerHit]:
    hits: list[FillerHit] = []
    lower = text.lower()
    for phrase in sorted(FILLER_PHRASES, key=len, reverse=True):
        start = 0
        while True:
            idx = lower.find(phrase, start)
            if idx < 0:
                break
            # word-ish boundaries
            before = lower[idx - 1] if idx > 0 else " "
            after_i = idx + len(phrase)
            after = lower[after_i] if after_i < len(lower) else " "
            if (not before.isalnum()) and (not after.isalnum()):
                hits.append(
                    FillerHit(
                        text=phrase,
                        start=None,
                        end=None,
                        char_start=idx,
                        char_length=len(phrase),
                    )
                )
            start = idx + len(phrase)

    for word in FILLER_WORDS:
        for m in re.finditer(rf"(?<![a-z]){re.escape(word)}(?![a-z])", lower):
            # skip if already inside a phrase hit
            if any(
                h.char_start is not None
                and h.char_start <= m.start() < (h.char_start + (h.char_length or 0))
                for h in hits
            ):
                continue
            hits.append(
                FillerHit(
                    text=word,
                    start=None,
                    end=None,
                    char_start=m.start(),
                    char_length=m.end() - m.start(),
                )
            )
    hits.sort(key=lambda h: h.char_start if h.char_start is not None else 0)
    return hits
