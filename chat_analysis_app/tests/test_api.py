from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.schemas import AnalyzeResponse, Metrics
from app.audio.wav import write_silence_wav
from app.main import app


@pytest.fixture()
def client(tmp_path):
    with TestClient(app, raise_server_exceptions=True) as c:
        # Force ready state without loading real models
        app.state.status = "ok"
        app.state.detail = None
        yield c


def test_health_ok(client):
    with patch("app.api.routes.transcriber") as tr, patch("app.api.routes.grammar_checker") as gc:
        tr.ready = True
        gc.ready = True
        res = client.get("/api/health")
        assert res.status_code == 200
        body = res.json()
        assert "faster-whisper" in body["model"]
        assert body["compute"] == "cpu/int8"
        assert body["offline"] is True


def test_analyze_requires_one_input(client):
    with patch("app.api.routes.transcriber") as tr, patch("app.api.routes.grammar_checker") as gc:
        tr.ready = True
        gc.ready = True
        res = client.post("/api/analyze", data={})
        assert res.status_code == 400


def test_analyze_text(client):
    fake = AnalyzeResponse(
        source="text",
        transcript="This are wrong.",
        coach_message="Grammar issue.",
        alerts=[],
        metrics=Metrics(grammar_count=1),
        suppressed="none",
    )
    with (
        patch("app.api.routes.transcriber") as tr,
        patch("app.api.routes.grammar_checker") as gc,
        patch("app.api.routes.analyze_text", return_value=fake) as at,
    ):
        tr.ready = True
        gc.ready = True
        res = client.post("/api/analyze", data={"text": "This are wrong."})
        assert res.status_code == 200
        assert res.json()["source"] == "text"
        at.assert_called_once()


def test_analyze_audio(client, tmp_path):
    path = tmp_path / "hello.wav"
    write_silence_wav(path, duration_sec=1.0)
    fake = AnalyzeResponse(
        source="audio",
        transcript="hello",
        coach_message="That sounded clear — no major issues from me.",
        alerts=[],
        metrics=Metrics(duration_sec=1.0),
        suppressed="none",
    )
    with (
        patch("app.api.routes.transcriber") as tr,
        patch("app.api.routes.grammar_checker") as gc,
        patch("app.api.routes.analyze_audio", return_value=fake),
    ):
        tr.ready = True
        gc.ready = True
        with path.open("rb") as f:
            res = client.post("/api/analyze", files={"audio": ("hello.wav", f, "audio/wav")})
        assert res.status_code == 200
        assert res.json()["transcript"] == "hello"


def test_503_when_loading(client):
    app.state.status = "loading"
    res = client.post("/api/analyze", data={"text": "hi"})
    assert res.status_code == 503
