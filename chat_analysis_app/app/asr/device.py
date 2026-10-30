"""Resolve ASR device: CUDA 11.8 GPU when available, else CPU."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceConfig:
    device: str  # cuda | cpu
    compute_type: str
    backend: str  # ctranslate2 | torch
    detail: str


def _env_device() -> str | None:
    raw = (os.environ.get("NORTHLINE_DEVICE") or "").strip().lower()
    if raw in {"cuda", "gpu"}:
        return "cuda"
    if raw in {"cpu"}:
        return "cpu"
    return None  # auto


def _ctranslate2_cuda_count() -> int:
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count() or 0)
    except Exception:  # noqa: BLE001
        return 0


def _torch_cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


def resolve_device() -> DeviceConfig:
    """
    Preference:
      1. NORTHLINE_DEVICE override
      2. CTranslate2 CUDA (faster-whisper) — typical on Linux GPU wheels
      3. PyTorch CUDA — used on Windows cu118 wheels when CT2 has no GPU
      4. CPU int8
    """
    forced = _env_device()
    ct2_gpus = _ctranslate2_cuda_count()
    torch_cuda = _torch_cuda_available()

    if forced == "cpu":
        return DeviceConfig("cpu", "int8", "ctranslate2", "forced cpu")

    if forced == "cuda":
        if ct2_gpus > 0:
            return DeviceConfig(
                "cuda",
                os.environ.get("NORTHLINE_COMPUTE_TYPE", "float16"),
                "ctranslate2",
                f"forced cuda via ctranslate2 ({ct2_gpus} device(s))",
            )
        if torch_cuda:
            return DeviceConfig(
                "cuda",
                "float16",
                "torch",
                "forced cuda via torch (Windows/cu118 path)",
            )
        logger.warning("NORTHLINE_DEVICE=cuda but no GPU backend found; using CPU")
        return DeviceConfig("cpu", "int8", "ctranslate2", "cuda requested but unavailable")

    # auto
    if ct2_gpus > 0:
        return DeviceConfig(
            "cuda",
            os.environ.get("NORTHLINE_COMPUTE_TYPE", "float16"),
            "ctranslate2",
            f"auto ctranslate2 cuda ({ct2_gpus} device(s))",
        )
    if torch_cuda:
        return DeviceConfig(
            "cuda",
            "float16",
            "torch",
            "auto torch cuda",
        )
    return DeviceConfig("cpu", "int8", "ctranslate2", "auto cpu")
