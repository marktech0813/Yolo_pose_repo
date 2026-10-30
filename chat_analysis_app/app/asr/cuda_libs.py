"""Put pip-installed NVIDIA CUDA 11.8 libs on the loader path (Linux/Windows)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_NVIDIA_PACKAGES = (
    "cuda_runtime",
    "cuda_nvrtc",
    "cublas",
    "cudnn",
    "cufft",
    "curand",
)


def prepend_cuda11_library_path() -> list[str]:
    """
    nvidia-*-cu11 wheels install shared libs under site-packages/nvidia/<pkg>/lib.
    CTranslate2 / torch need these discoverable at runtime on offline machines.
    """
    roots: list[Path] = []
    for entry in sys.path:
        nvidia = Path(entry) / "nvidia"
        if nvidia.is_dir():
            roots.append(nvidia)

    added: list[str] = []
    for root in roots:
        for name in _NVIDIA_PACKAGES:
            lib = root / name / "lib"
            if not lib.is_dir():
                # some wheels use lib64 or bin
                alt = root / name / "bin"
                lib = lib if lib.is_dir() else alt
            if lib.is_dir():
                path = str(lib.resolve())
                if path not in added:
                    added.append(path)

    if not added:
        return []

    if sys.platform == "win32":
        # Windows loads from PATH
        path_key = "PATH"
        sep = ";"
    else:
        path_key = "LD_LIBRARY_PATH"
        sep = ":"

    current = os.environ.get(path_key, "")
    parts = [p for p in current.split(sep) if p]
    for p in reversed(added):
        if p in parts:
            parts.remove(p)
        parts.insert(0, p)
    os.environ[path_key] = sep.join(parts)
    logger.info("CUDA 11.8 library path primed (%d entries)", len(added))
    return added
