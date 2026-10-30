"""Request/response shapes for the analyze API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AlertKind = Literal[
    "grammar",
    "spelling",
    "accent",
    "pronunciation",  # alias kept for older clients
    "recognition",
    "filler",
    "pause",
    "repeat",
    "rate",
]
WordStatus = Literal["correct", "grammar", "spelling", "accent", "filler", "recognition"]
Severity = Literal["info", "warn"]
Suppressed = Literal["none", "no_speech", "low_confidence"]
Source = Literal["audio", "text"]


class Alert(BaseModel):
    kind: AlertKind
    severity: Severity = "warn"
    message: str
    start: float | None = None
    end: float | None = None
    char_start: int | None = None
    char_length: int | None = None
    text: str | None = None
    replacements: list[str] = Field(default_factory=list)
    confidence: float | None = None


class WordReview(BaseModel):
    """Per-word correct / issue tag for the recognized sentence."""

    text: str
    status: WordStatus = "correct"
    char_start: int
    char_length: int
    confidence: float | None = None
    message: str | None = None
    replacements: list[str] = Field(default_factory=list)


class Metrics(BaseModel):
    duration_sec: float | None = None
    wpm: float | None = None
    filler_count: int = 0
    pause_count: int = 0
    grammar_count: int = 0
    spelling_count: int = 0
    unclear_count: int = 0
    correct_count: int = 0
    word_count: int = 0


class AnalyzeResponse(BaseModel):
    source: Source
    transcript: str
    coach_message: str
    alerts: list[Alert]
    word_reviews: list[WordReview] = Field(default_factory=list)
    metrics: Metrics
    suppressed: Suppressed = "none"


class HealthResponse(BaseModel):
    status: Literal["loading", "ok", "error"]
    whisper_ready: bool
    languagetool_ready: bool
    model: str
    compute: str
    device: str = "cpu"
    backend: str = "ctranslate2"
    cuda: bool = False
    offline: bool = True
    detail: str | None = None
