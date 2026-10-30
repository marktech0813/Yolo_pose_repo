"""HTTP routes for health and analyze."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app import config
from app.api.schemas import AnalyzeResponse, HealthResponse
from app.asr.transcriber import transcriber
from app.audio.wav import WavError, parse_wav
from app.grammar.checker import grammar_checker
from app.pipeline import analyze_audio, analyze_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

_asr_lock = asyncio.Lock()


def _app_state(request: Request):
    return request.app.state


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    state = _app_state(request)
    status = getattr(state, "status", "loading")
    detail = getattr(state, "detail", None)
    device = config.WHISPER_DEVICE
    compute = f"{device}/{config.WHISPER_COMPUTE_TYPE}"
    return HealthResponse(
        status=status,
        whisper_ready=transcriber.ready,
        languagetool_ready=grammar_checker.ready,
        model=f"faster-whisper-{config.WHISPER_MODEL_NAME}",
        compute=compute,
        device=device,
        backend=getattr(config, "WHISPER_BACKEND", "ctranslate2"),
        cuda=device == "cuda",
        offline=True,
        detail=detail,
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: Request,
    audio: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
) -> AnalyzeResponse:
    state = _app_state(request)
    if getattr(state, "status", "loading") != "ok":
        raise HTTPException(
            status_code=503,
            detail=getattr(state, "detail", None) or "Models are still loading",
        )
    if not transcriber.ready or not grammar_checker.ready:
        raise HTTPException(status_code=503, detail="Models are not ready")

    has_audio = audio is not None and audio.filename is not None
    # Treat empty upload as absent
    if audio is not None and not audio.filename:
        has_audio = False

    text_value = (text or "").strip() if text is not None else ""
    has_text = bool(text_value)

    if has_audio and has_text:
        raise HTTPException(status_code=400, detail="Provide exactly one of audio or text")
    if not has_audio and not has_text:
        raise HTTPException(status_code=400, detail="Provide exactly one of audio or text")

    if has_text:
        if len(text_value) > config.MAX_TEXT_CHARS:
            raise HTTPException(status_code=400, detail="Text exceeds character limit")
        return await asyncio.to_thread(analyze_text, text_value)

    assert audio is not None
    data = await audio.read()
    if len(data) > config.MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Audio exceeds size limit")
    try:
        wav = parse_wav(data)
    except WavError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async with _asr_lock:
        return await asyncio.to_thread(analyze_audio, wav)
