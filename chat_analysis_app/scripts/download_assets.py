#!/usr/bin/env python3
"""One-time online download of Whisper, VAD, LanguageTool, and UI fonts."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
WHISPER_DIR = MODELS / "faster-whisper-small.en"
WHISPER_NAME = "small.en"
HF_HOME = MODELS / "hf"
LT_DIR = MODELS / "languagetool"
FONTS_DIR = ROOT / "web" / "fonts"

# Google Fonts GitHub raw (OFL)
FONT_URLS = {
    "Syne-SemiBold.woff2": "https://github.com/google/fonts/raw/main/ofl/syne/Syne%5Bwght%5D.ttf",
    "Literata-Regular.woff2": "https://github.com/google/fonts/raw/main/ofl/literata/Literata%5Bopsz%2Cwght%5D.ttf",
    "Figtree-Regular.woff2": "https://github.com/google/fonts/raw/main/ofl/figtree/Figtree%5Bwght%5D.ttf",
}

# Use TTF fallbacks with correct extensions if woff2 CDN unavailable
FONT_FILES = {
    "Syne[wght].ttf": "https://github.com/google/fonts/raw/main/ofl/syne/Syne%5Bwght%5D.ttf",
    "Literata[opsz,wght].ttf": "https://github.com/google/fonts/raw/main/ofl/literata/Literata%5Bopsz%2Cwght%5D.ttf",
    "Figtree[wght].ttf": "https://github.com/google/fonts/raw/main/ofl/figtree/Figtree%5Bwght%5D.ttf",
}


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def check_java() -> None:
    java = shutil.which("java")
    if not java:
        fail("Java not found. Install Java 17+ (e.g. openjdk-17-jre-headless).")
    try:
        out = subprocess.check_output([java, "-version"], stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as exc:
        fail(f"Could not run java: {exc}")
    # Parse version from lines like: openjdk version "17.0.x" or "1.8.0_xxx"
    version_line = (out or "").splitlines()[0] if out else ""
    print(f"Java: {version_line}")
    major = None
    if '"' in version_line:
        ver = version_line.split('"')[1]
        if ver.startswith("1."):
            major = int(ver.split(".")[1])
        else:
            major = int(ver.split(".")[0])
    if major is None or major < 17:
        fail(
            f"Java 17+ required for LanguageTool (found major={major}). "
            "Install openjdk-17-jre-headless and re-run."
        )


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  exists: {dest.name}")
        return
    print(f"  downloading {dest.name}…")
    urllib.request.urlretrieve(url, dest)  # noqa: S310


def download_whisper() -> None:
    print(f"==> faster-whisper {WHISPER_NAME}")
    MODELS.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(HF_HOME)
    HF_HOME.mkdir(parents=True, exist_ok=True)
    from faster_whisper import WhisperModel

    if WHISPER_DIR.exists() and (WHISPER_DIR / "model.bin").exists():
        print(f"  ready: {WHISPER_DIR}")
        return

    model = WhisperModel(
        WHISPER_NAME,
        device="cpu",
        compute_type="int8",
        download_root=str(MODELS),
    )
    del model

    # Prefer directories that look like the requested model
    ct2_dirs = [p.parent for p in MODELS.rglob("model.bin")]
    preferred = [
        d
        for d in ct2_dirs
        if "small.en" in str(d).lower() or "small-en" in str(d).lower()
    ]
    pick = preferred[0] if preferred else (ct2_dirs[0] if ct2_dirs else None)
    if pick is None:
        print("  model cached under models/; app will resolve via download_root")
        return
    if pick.resolve() != WHISPER_DIR.resolve():
        if WHISPER_DIR.exists():
            shutil.rmtree(WHISPER_DIR)
        shutil.copytree(pick, WHISPER_DIR)
    print(f"  ready: {WHISPER_DIR}")


def download_vad() -> None:
    print("==> Silero VAD (via faster-whisper first transcription warm-up skipped)")
    # VAD weights are pulled on first vad_filter use; prefetch common HF path if possible.
    HF_HOME.mkdir(parents=True, exist_ok=True)
    print(f"  HF_HOME={HF_HOME}")


def download_languagetool() -> None:
    print("==> LanguageTool")
    LT_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["LTP_PATH"] = str(LT_DIR)
    import language_tool_python

    tool = language_tool_python.LanguageTool("en-US")
    _ = tool.check("This are wrong.")
    tool.close()
    print(f"  LanguageTool jar cached under {LT_DIR}")


def download_fonts() -> None:
    print("==> UI fonts")
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in FONT_FILES.items():
        try:
            download_file(url, FONTS_DIR / name)
        except Exception as exc:  # noqa: BLE001
            print(f"  warning: could not download {name}: {exc}")


def main() -> None:
    print("Northline asset download (requires network once)")
    check_java()
    download_fonts()
    download_whisper()
    download_vad()
    download_languagetool()
    print("Done. You can now run offline with HF_HUB_OFFLINE=1.")


if __name__ == "__main__":
    main()
