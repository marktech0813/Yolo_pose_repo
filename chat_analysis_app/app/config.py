"""Paths, caps, and analysis thresholds."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
MODELS_DIR = ROOT / "models"
WHISPER_MODEL_DIR = MODELS_DIR / "faster-whisper-small.en"
HF_HOME = MODELS_DIR / "hf"
LANGUAGETOOL_DIR = MODELS_DIR / "languagetool"

# ASR — small.en; device/compute resolved at runtime (CUDA 11.8 GPU or CPU)
WHISPER_MODEL_NAME = "small.en"
WHISPER_TORCH_MODEL = "small"  # openai-whisper name for Windows cu118 path
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_BACKEND = "ctranslate2"
WHISPER_LANGUAGE = "en"
WHISPER_BEAM_SIZE = 5
WHISPER_INITIAL_PROMPT = (
    "Clear American English speech for grammar and pronunciation coaching."
)

# LanguageTool
LT_LANGUAGE = "en-US"
LT_KEEP_CATEGORIES = frozenset({"GRAMMAR", "TYPOS", "CASING"})
LT_DROP_CATEGORIES = frozenset({"STYLE", "TYPOGRAPHY", "WHITESPACE", "MISC", "SEMANTICS"})

# Audio caps
SAMPLE_RATE = 16_000
MAX_AUDIO_SECONDS = 60.0
MIN_AUDIO_SECONDS = 0.3
MAX_BODY_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 2000

# Pronunciation / native-accent heuristics (ASR word confidence)
PRONUNCIATION_PROB_THRESHOLD = 0.55
MIN_PRONUNCIATION_WORD_LEN = 3
NO_SPEECH_PROB_THRESHOLD = 0.6
MEAN_PROB_GATE = 0.30
ACCENT_SOFT_THRESHOLD = 0.70  # below this → soft accent caution if not already flagged

FUNCTION_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "for",
        "is",
        "it",
        "that",
        "this",
    }
)

# Fluency
PAUSE_SECONDS = 0.8
SLOW_WPM = 90
FAST_WPM = 180
MIN_SPEECH_SECONDS_FOR_RATE = 5.0
FILLER_RATE_PER_100 = 4
FILLER_ABSOLUTE_MIN = 3

# Coach
MAX_COACH_POINTS = 3

HOST = "127.0.0.1"
PORT = 8000
