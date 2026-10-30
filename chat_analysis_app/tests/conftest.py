"""Prevent real model downloads during unit tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _stub_model_loads(monkeypatch):
    from app.asr.transcriber import transcriber
    from app.grammar.checker import grammar_checker

    def fake_whisper_load():
        transcriber._model = object()

    def fake_lt_load():
        grammar_checker._tool = object()

    def fake_lt_close():
        grammar_checker._tool = None

    monkeypatch.setattr(transcriber, "load", fake_whisper_load)
    monkeypatch.setattr(grammar_checker, "load", fake_lt_load)
    monkeypatch.setattr(grammar_checker, "close", fake_lt_close)
