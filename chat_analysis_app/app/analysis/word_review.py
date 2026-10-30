"""Build per-word correct / issue reviews for the recognized sentence."""

from __future__ import annotations

import re
from typing import Iterable

from app.api.schemas import Alert, WordReview
from app.asr.transcriber import WordTiming
from app.grammar.checker import spans_overlap


_TOKEN_RE = re.compile(r"[A-Za-z0-9']+|[^\sA-Za-z0-9']+")


def tokenize_with_spans(text: str) -> list[tuple[str, int, int]]:
    """Split transcript into display tokens with char offsets (keeps punctuation)."""
    out: list[tuple[str, int, int]] = []
    for m in _TOKEN_RE.finditer(text):
        tok = m.group(0)
        if tok.isspace():
            continue
        out.append((tok, m.start(), m.end() - m.start()))
    return out


def _alert_priority(kind: str) -> int:
    order = {
        "recognition": 0,
        "grammar": 1,
        "spelling": 2,
        "accent": 3,
        "pronunciation": 3,
        "filler": 4,
    }
    return order.get(kind, 99)


def _status_for_kind(kind: str) -> str:
    if kind == "pronunciation":
        return "accent"
    if kind in {"grammar", "spelling", "accent", "filler", "recognition"}:
        return kind
    return "correct"


def build_word_reviews(
    text: str,
    alerts: Iterable[Alert],
    words: list[WordTiming] | None = None,
) -> list[WordReview]:
    tokens = tokenize_with_spans(text)
    if not tokens:
        return []

    alert_list = list(alerts)
    # Map ASR confidence onto letter tokens when available
    conf_by_span: list[tuple[int, int, float]] = []
    if words:
        cursor = 0
        lower = text
        for w in words:
            token = w.word.strip()
            if not token:
                continue
            idx = lower.find(token, cursor)
            if idx < 0:
                idx = lower.lower().find(token.lower(), cursor)
            if idx < 0:
                continue
            conf_by_span.append((idx, len(token), float(w.probability)))
            cursor = idx + len(token)

    reviews: list[WordReview] = []
    for tok, start, length in tokens:
        # Punctuation-only → correct, no issue tagging
        if not re.search(r"[A-Za-z0-9]", tok):
            reviews.append(
                WordReview(text=tok, status="correct", char_start=start, char_length=length)
            )
            continue

        hit: Alert | None = None
        for a in alert_list:
            if a.char_start is None or not a.char_length:
                continue
            if _status_for_kind(a.kind) == "correct":
                continue
            if spans_overlap(start, length, a.char_start, a.char_length):
                if hit is None or _alert_priority(a.kind) < _alert_priority(hit.kind):
                    hit = a

        confidence = None
        for cs, cl, prob in conf_by_span:
            if spans_overlap(start, length, cs, cl):
                confidence = prob
                break

        if hit is None:
            reviews.append(
                WordReview(
                    text=tok,
                    status="correct",
                    char_start=start,
                    char_length=length,
                    confidence=confidence,
                )
            )
        else:
            reviews.append(
                WordReview(
                    text=tok,
                    status=_status_for_kind(hit.kind),  # type: ignore[arg-type]
                    char_start=start,
                    char_length=length,
                    confidence=confidence if confidence is not None else hit.confidence,
                    message=hit.message,
                    replacements=list(hit.replacements or []),
                )
            )
    return reviews
