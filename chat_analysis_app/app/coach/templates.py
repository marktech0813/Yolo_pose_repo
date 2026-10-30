"""Template strings for coach replies."""

from __future__ import annotations

EMPTY_AUDIO = (
    "I didn’t catch any clear speech. Try speaking a little closer to the mic."
)
LOW_CONFIDENCE = (
    "That was hard to recognize clearly. Please say it again a bit slower."
)
CLEAN = "I heard you clearly — grammar, spelling, and accent look solid."
NEXT_STEP = "Try saying the corrected sentence once more."
HEARD_PREFIX = "I heard:"

KIND_OPENERS = {
    "recognition": "I may have misheard “{text}”.",
    "grammar": "Grammar: {message}",
    "spelling": "Spelling: check “{text}”.",
    "accent": "Accent: “{text}” did not sound fully native — say it more clearly.",
    "pronunciation": "Accent: “{text}” did not sound fully native — say it more clearly.",
    "filler": "Try dropping the filler “{text}”.",
    "repeat": "You repeated “{text}” — one time is enough.",
    "pause": "There was a long pause — keep the thought moving.",
    "rate": "{message}",
}


def with_replacements(base: str, replacements: list[str]) -> str:
    if not replacements:
        return base
    shown = ", ".join(f"“{r}”" for r in replacements[:3])
    return f"{base} Suggestion: {shown}."
