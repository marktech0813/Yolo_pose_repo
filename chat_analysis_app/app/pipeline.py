"""One-turn analysis orchestration and overlap gates."""

from __future__ import annotations

import logging
import re
from typing import Literal

from app import config
from app.analysis.word_review import build_word_reviews
from app.api.schemas import Alert, AnalyzeResponse, Metrics
from app.asr.transcriber import TranscriptResult, WordTiming, transcriber
from app.audio.wav import WavAudio
from app.coach.compose import compose_message
from app.fluency.fillers import find_fillers_in_text, find_fillers_in_words
from app.fluency.metrics import compute_fluency
from app.grammar.checker import GrammarMatch, char_span_for_word, grammar_checker, spans_overlap
from app.pronunciation.alerts import find_pronunciation_alerts

logger = logging.getLogger(__name__)

Source = Literal["audio", "text"]


def _filler_char_ranges(text: str, filler_hits) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for h in filler_hits:
        if h.char_start is not None and h.char_length:
            ranges.append((h.char_start, h.char_length))
            continue
        m = re.search(re.escape(h.text), text, re.IGNORECASE)
        if m:
            ranges.append((m.start(), m.end() - m.start()))
    return ranges


def _match_in_filler(match: GrammarMatch, filler_ranges: list[tuple[int, int]]) -> bool:
    return any(spans_overlap(match.offset, match.length, fs, fl) for fs, fl in filler_ranges)


def _finalize(
    *,
    source: Source,
    text: str,
    alerts: list[Alert],
    metrics: Metrics,
    suppressed: str,
    words: list[WordTiming] | None = None,
) -> AnalyzeResponse:
    reviews = build_word_reviews(text, alerts, words=words)
    correct = sum(1 for r in reviews if r.status == "correct" and re.search(r"[A-Za-z0-9]", r.text))
    word_count = sum(1 for r in reviews if re.search(r"[A-Za-z0-9]", r.text))
    metrics.correct_count = correct
    metrics.word_count = word_count
    coach = compose_message([a.model_dump() for a in alerts], suppressed=suppressed)
    return AnalyzeResponse(
        source=source,
        transcript=text,
        coach_message=coach,
        alerts=alerts,
        word_reviews=reviews,
        metrics=metrics,
        suppressed=suppressed,  # type: ignore[arg-type]
    )


def analyze_text(text: str) -> AnalyzeResponse:
    cleaned = text.strip()
    grammar = grammar_checker.check(cleaned)
    fillers = find_fillers_in_text(cleaned)
    filler_ranges = _filler_char_ranges(cleaned, fillers)

    alerts: list[Alert] = []
    grammar_count = 0
    spelling_count = 0

    for m in grammar.matches:
        if _match_in_filler(m, filler_ranges):
            continue
        if m.kind == "spelling":
            spelling_count += 1
            alerts.append(
                Alert(
                    kind="spelling",
                    severity="warn",
                    message=m.message or f"Check spelling of “{m.text}”.",
                    char_start=m.offset,
                    char_length=m.length,
                    text=m.text,
                    replacements=m.replacements,
                )
            )
        else:
            grammar_count += 1
            alerts.append(
                Alert(
                    kind="grammar",
                    severity="warn",
                    message=m.message or "Grammar issue.",
                    char_start=m.offset,
                    char_length=m.length,
                    text=m.text,
                    replacements=m.replacements,
                )
            )

    word_count = max(1, len(re.findall(r"[A-Za-z']+", cleaned)))
    filler_count = len(fillers)
    if filler_count >= config.FILLER_ABSOLUTE_MIN or (
        filler_count / word_count * 100 >= config.FILLER_RATE_PER_100 and filler_count >= 1
    ):
        for h in fillers[:5]:
            alerts.append(
                Alert(
                    kind="filler",
                    severity="info",
                    message=f"Filler “{h.text}”.",
                    char_start=h.char_start,
                    char_length=h.char_length,
                    text=h.text,
                )
            )

    return _finalize(
        source="text",
        text=cleaned,
        alerts=alerts,
        metrics=Metrics(
            duration_sec=None,
            wpm=None,
            filler_count=filler_count,
            pause_count=0,
            grammar_count=grammar_count,
            spelling_count=spelling_count,
            unclear_count=0,
        ),
        suppressed="none",
    )


def analyze_audio(wav: WavAudio) -> AnalyzeResponse:
    result: TranscriptResult = transcriber.transcribe(wav.samples, wav.sample_rate)

    if result.no_speech_prob >= config.NO_SPEECH_PROB_THRESHOLD or not result.words:
        return _finalize(
            source="audio",
            text=result.text or "",
            alerts=[],
            metrics=Metrics(duration_sec=result.duration_sec or wav.duration_sec),
            suppressed="no_speech",
            words=result.words,
        )

    mean_prob = result.mean_word_probability
    if mean_prob is not None and mean_prob < config.MEAN_PROB_GATE:
        alerts = [
            Alert(
                kind="recognition",
                severity="warn",
                message="Speech was hard to recognize. Please speak slower and closer to the mic.",
                text=result.text[:80],
            )
        ]
        return _finalize(
            source="audio",
            text=result.text,
            alerts=alerts,
            metrics=Metrics(
                duration_sec=result.duration_sec,
                unclear_count=len(result.words),
            ),
            suppressed="low_confidence",
            words=result.words,
        )

    text = result.text
    grammar = grammar_checker.check(text)
    fillers = find_fillers_in_words(result.words)
    text_fillers = find_fillers_in_text(text)
    filler_ranges = _filler_char_ranges(text, text_fillers)
    fluency = compute_fluency(result.words)
    pron = find_pronunciation_alerts(result.words)

    pron_char: list[tuple[int, int] | None] = []
    seen: dict[str, int] = {}
    for p in pron:
        key = p.word.strip().lower()
        occ = seen.get(key, 0)
        seen[key] = occ + 1
        span = char_span_for_word(text, p.word.strip(), occurrence=occ)
        pron_char.append(span)

    spelling_matches = [m for m in grammar.matches if m.kind == "spelling"]
    grammar_matches = [m for m in grammar.matches if m.kind == "grammar"]

    recognition_alerts: list[Alert] = []
    used_spelling: set[int] = set()
    used_pron: set[int] = set()

    for pi, p in enumerate(pron):
        span = pron_char[pi]
        if span is None:
            continue
        cs, cl = span
        for si, sm in enumerate(spelling_matches):
            if si in used_spelling:
                continue
            if spans_overlap(cs, cl, sm.offset, sm.length):
                recognition_alerts.append(
                    Alert(
                        kind="recognition",
                        severity="warn",
                        message=f"I may have misheard “{p.word.strip()}”.",
                        start=p.start,
                        end=p.end,
                        char_start=cs,
                        char_length=cl,
                        text=p.word.strip(),
                        replacements=sm.replacements,
                        confidence=p.probability,
                    )
                )
                used_spelling.add(si)
                used_pron.add(pi)
                break

    alerts: list[Alert] = []
    alerts.extend(recognition_alerts)

    grammar_count = 0
    spelling_count = 0
    for m in grammar_matches:
        if _match_in_filler(m, filler_ranges):
            continue
        grammar_count += 1
        alerts.append(
            Alert(
                kind="grammar",
                severity="warn",
                message=m.message or "Grammar issue.",
                char_start=m.offset,
                char_length=m.length,
                text=m.text,
                replacements=m.replacements,
            )
        )

    for si, sm in enumerate(spelling_matches):
        if si in used_spelling:
            continue
        if _match_in_filler(sm, filler_ranges):
            continue
        spelling_count += 1
        alerts.append(
            Alert(
                kind="spelling",
                severity="warn",
                message=sm.message or f"Check spelling of “{sm.text}”.",
                char_start=sm.offset,
                char_length=sm.length,
                text=sm.text,
                replacements=sm.replacements,
            )
        )

    unclear_count = 0
    for pi, p in enumerate(pron):
        if pi in used_pron:
            continue
        # Soft accent tips only when no harder issues on that span yet
        span = pron_char[pi]
        if p.severity == "soft":
            if span is None:
                continue
            if any(
                a.char_start is not None
                and a.char_length
                and spans_overlap(span[0], span[1], a.char_start, a.char_length)
                for a in alerts
            ):
                continue
        unclear_count += 1
        alerts.append(
            Alert(
                kind="accent",
                severity="warn" if p.severity == "warn" else "info",
                message=(
                    f"“{p.word.strip()}” may not match a native accent — practice this word."
                    if p.severity == "warn"
                    else f"“{p.word.strip()}” could sound clearer / more native."
                ),
                start=p.start,
                end=p.end,
                char_start=span[0] if span else None,
                char_length=span[1] if span else None,
                text=p.word.strip(),
                confidence=p.probability,
            )
        )

    word_count = max(1, len(result.words))
    filler_count = len(fillers)
    if filler_count >= config.FILLER_ABSOLUTE_MIN or (
        filler_count / word_count * 100 >= config.FILLER_RATE_PER_100 and filler_count >= 1
    ):
        for h in fillers[:5]:
            # attach char span for fillers
            m = re.search(re.escape(h.text), text, re.IGNORECASE)
            alerts.append(
                Alert(
                    kind="filler",
                    severity="info",
                    message=f"Filler “{h.text}”.",
                    start=h.start,
                    end=h.end,
                    char_start=m.start() if m else None,
                    char_length=(m.end() - m.start()) if m else None,
                    text=h.text,
                )
            )

    for r in fluency.repeats[:2]:
        alerts.append(
            Alert(
                kind="repeat",
                severity="info",
                message=f"Repeated “{r.word}”.",
                start=r.start,
                end=r.end,
                text=r.word,
            )
        )

    for p in fluency.pauses[:2]:
        alerts.append(
            Alert(
                kind="pause",
                severity="info",
                message=f"Long pause ({p.duration:.1f}s).",
                start=p.start,
                end=p.end,
                text="",
            )
        )

    if fluency.wpm is not None:
        if fluency.wpm < config.SLOW_WPM:
            alerts.append(
                Alert(
                    kind="rate",
                    severity="info",
                    message=f"Speaking rate is slow (~{fluency.wpm:.0f} WPM). Try a steadier pace.",
                    text=f"{fluency.wpm:.0f} WPM",
                )
            )
        elif fluency.wpm > config.FAST_WPM:
            alerts.append(
                Alert(
                    kind="rate",
                    severity="info",
                    message=f"Speaking rate is fast (~{fluency.wpm:.0f} WPM). Slow down a little.",
                    text=f"{fluency.wpm:.0f} WPM",
                )
            )

    return _finalize(
        source="audio",
        text=text,
        alerts=alerts,
        metrics=Metrics(
            duration_sec=result.duration_sec,
            wpm=fluency.wpm,
            filler_count=filler_count,
            pause_count=len(fluency.pauses),
            grammar_count=grammar_count,
            spelling_count=spelling_count,
            unclear_count=unclear_count,
        ),
        suppressed="none",
        words=result.words,
    )
