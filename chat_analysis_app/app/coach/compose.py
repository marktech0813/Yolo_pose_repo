"""Compose a short template coach reply from prioritized alerts."""

from __future__ import annotations

from app import config
from app.coach import templates


PRIORITY = (
    "recognition",
    "grammar",
    "spelling",
    "accent",
    "pronunciation",
    "filler",
    "repeat",
    "pause",
    "rate",
)


def _line_for(alert: dict) -> str:
    kind = alert.get("kind", "")
    text = alert.get("text") or ""
    message = alert.get("message") or ""
    pattern = templates.KIND_OPENERS.get(kind, message or text)
    line = pattern.format(text=text, message=message)
    if kind in {"grammar", "spelling", "recognition"}:
        line = templates.with_replacements(line, alert.get("replacements") or [])
    return line


def compose_message(
    alerts: list[dict],
    *,
    suppressed: str = "none",
) -> str:
    if suppressed == "no_speech":
        return templates.EMPTY_AUDIO
    if suppressed == "low_confidence":
        return templates.LOW_CONFIDENCE

    if not alerts:
        return templates.CLEAN

    by_kind = {k: [] for k in PRIORITY}
    for a in alerts:
        kind = a.get("kind")
        if kind in by_kind:
            by_kind[kind].append(a)

    chosen: list[dict] = []
    for kind in PRIORITY:
        for a in by_kind[kind]:
            chosen.append(a)
            if len(chosen) >= config.MAX_COACH_POINTS:
                break
        if len(chosen) >= config.MAX_COACH_POINTS:
            break

    lines = [_line_for(a) for a in chosen]
    if any(
        a.get("kind") in {"grammar", "spelling", "accent", "pronunciation", "recognition"}
        for a in chosen
    ):
        lines.append(templates.NEXT_STEP)
    return " ".join(lines)
