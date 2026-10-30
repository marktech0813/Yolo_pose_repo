"""Northline FastAPI entrypoint."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.api.routes import router
from app.asr.transcriber import transcriber
from app.grammar.checker import grammar_checker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("northline")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.status = "loading"
    app.state.detail = "Loading offline models…"
    # Prefer local caches for offline use
    os.environ.setdefault("HF_HOME", str(config.HF_HOME))
    os.environ.setdefault("LTP_PATH", str(config.LANGUAGETOOL_DIR))
    config.HF_HOME.mkdir(parents=True, exist_ok=True)
    config.LANGUAGETOOL_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from app.asr.cuda_libs import prepend_cuda11_library_path

        prepend_cuda11_library_path()
        logger.info("Startup: resolving ASR device (CUDA 11.8 GPU if present)")
        transcriber.load()
        grammar_checker.load()
        app.state.status = "ok"
        app.state.detail = None
        dc = transcriber.device_config
        logger.info(
            "Northline ready (%s)",
            f"{dc.backend}/{dc.device}/{dc.compute_type}" if dc else "unknown",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load models")
        app.state.status = "error"
        app.state.detail = str(exc)
    try:
        yield
    finally:
        grammar_checker.close()


app = FastAPI(title="Northline", version="0.1.0", lifespan=lifespan)
app.include_router(router)

# Static assets
if config.WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(config.WEB_DIR)), name="static")


@app.get("/")
async def index():
    index_path = config.WEB_DIR / "index.html"
    if not index_path.exists():
        return {"detail": "UI not found. Ensure web/index.html exists."}
    return FileResponse(index_path)


# Serve css/js/fonts/assets at root-relative paths used by index.html
@app.get("/css/{path:path}")
async def css(path: str):
    file_path = config.WEB_DIR / "css" / path
    if not file_path.is_file():
        return _not_found()
    return FileResponse(file_path)


@app.get("/js/{path:path}")
async def js(path: str):
    file_path = config.WEB_DIR / "js" / path
    if not file_path.is_file():
        return _not_found()
    return FileResponse(file_path)


@app.get("/fonts/{path:path}")
async def fonts(path: str):
    file_path = config.WEB_DIR / "fonts" / path
    if not file_path.is_file():
        return _not_found()
    return FileResponse(file_path)


@app.get("/assets/{path:path}")
async def assets(path: str):
    file_path = config.WEB_DIR / "assets" / path
    if not file_path.is_file():
        return _not_found()
    return FileResponse(file_path)


def _not_found():
    from fastapi.responses import JSONResponse

    return JSONResponse({"detail": "Not found"}, status_code=404)
