"""ASR wrapper: faster-whisper (CTranslate2) or torch Whisper, CPU/CUDA."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app import config
from app.asr.device import DeviceConfig, resolve_device

logger = logging.getLogger(__name__)


@dataclass
class WordTiming:
    word: str
    start: float
    end: float
    probability: float


@dataclass
class TranscriptResult:
    text: str
    duration_sec: float
    no_speech_prob: float
    avg_logprob: float
    words: list[WordTiming] = field(default_factory=list)

    @property
    def mean_word_probability(self) -> float | None:
        if not self.words:
            return None
        return sum(w.probability for w in self.words) / len(self.words)


def _normalize_audio(audio: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak < 1e-6:
        return audio
    target = 0.9
    if peak < target:
        audio = audio * (target / peak)
    return np.clip(audio, -1.0, 1.0).astype(np.float32)


class Transcriber:
    def __init__(self) -> None:
        self._model: Any = None
        self._backend: str | None = None
        self.device_config: DeviceConfig | None = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        self.device_config = resolve_device()
        cfg = self.device_config
        # Mirror into config for health / logs
        config.WHISPER_DEVICE = cfg.device
        config.WHISPER_COMPUTE_TYPE = cfg.compute_type
        config.WHISPER_BACKEND = cfg.backend

        logger.info(
            "ASR resolve: device=%s compute=%s backend=%s (%s)",
            cfg.device,
            cfg.compute_type,
            cfg.backend,
            cfg.detail,
        )

        if cfg.backend == "torch":
            self._load_torch(cfg)
        else:
            self._load_ctranslate2(cfg)

    def _model_path(self) -> tuple[str, bool]:
        local_only = (config.WHISPER_MODEL_DIR / "model.bin").exists()
        if local_only:
            return str(config.WHISPER_MODEL_DIR), True
        return config.WHISPER_MODEL_NAME, False

    def _load_ctranslate2(self, cfg: DeviceConfig) -> None:
        from faster_whisper import WhisperModel

        model_path, local_only = self._model_path()
        self._model = WhisperModel(
            model_path,
            device=cfg.device,
            compute_type=cfg.compute_type,
            download_root=str(config.MODELS_DIR),
            local_files_only=local_only,
            device_index=0,
        )
        self._backend = "ctranslate2"
        logger.info(
            "Whisper ready via ctranslate2 (%s/%s, %s)",
            cfg.device,
            cfg.compute_type,
            config.WHISPER_MODEL_NAME,
        )

    def _load_torch(self, cfg: DeviceConfig) -> None:
        """Windows cu118 path: openai-whisper on CUDA."""
        import whisper

        name = config.WHISPER_TORCH_MODEL
        # Prefer local cache under models/
        download_root = str(config.MODELS_DIR / "torch-whisper")
        self._model = whisper.load_model(name, device=cfg.device, download_root=download_root)
        self._backend = "torch"
        logger.info("Whisper ready via torch (%s, model=%s)", cfg.device, name)

    def transcribe(self, samples: list[float], sample_rate: int) -> TranscriptResult:
        if self._model is None:
            raise RuntimeError("Whisper model not loaded")
        audio = _normalize_audio(np.asarray(samples, dtype=np.float32))
        if self._backend == "torch":
            return self._transcribe_torch(audio, sample_rate)
        return self._transcribe_ct2(audio, sample_rate)

    def _transcribe_ct2(self, audio: np.ndarray, sample_rate: int) -> TranscriptResult:
        segments, info = self._model.transcribe(
            audio,
            language=config.WHISPER_LANGUAGE,
            beam_size=config.WHISPER_BEAM_SIZE,
            best_of=config.WHISPER_BEAM_SIZE,
            patience=1.0,
            temperature=0.0,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=400,
                speech_pad_ms=200,
            ),
            condition_on_previous_text=False,
            initial_prompt=config.WHISPER_INITIAL_PROMPT,
            without_timestamps=False,
        )

        words: list[WordTiming] = []
        texts: list[str] = []
        no_speech_probs: list[float] = []
        avg_logprobs: list[float] = []
        last_end = 0.0

        for segment in segments:
            texts.append(segment.text.strip())
            no_speech_probs.append(float(getattr(segment, "no_speech_prob", 0.0) or 0.0))
            avg_logprobs.append(float(getattr(segment, "avg_logprob", 0.0) or 0.0))
            last_end = max(last_end, float(segment.end or 0.0))
            for w in segment.words or []:
                token = (w.word or "").strip()
                if not token:
                    continue
                words.append(
                    WordTiming(
                        word=token,
                        start=float(w.start or 0.0),
                        end=float(w.end or 0.0),
                        probability=float(w.probability or 0.0),
                    )
                )

        joined = " ".join(t for t in texts if t).strip()
        while "  " in joined:
            joined = joined.replace("  ", " ")

        duration = float(getattr(info, "duration", 0.0) or last_end or (len(audio) / sample_rate))
        return TranscriptResult(
            text=joined,
            duration_sec=duration,
            no_speech_prob=max(no_speech_probs) if no_speech_probs else 1.0,
            avg_logprob=(sum(avg_logprobs) / len(avg_logprobs)) if avg_logprobs else -10.0,
            words=words,
        )

    def _transcribe_torch(self, audio: np.ndarray, sample_rate: int) -> TranscriptResult:
        import whisper

        # openai-whisper expects 16 kHz float32 mono
        if sample_rate != 16000:
            # simple resample via linear interpolation
            duration = len(audio) / float(sample_rate)
            new_len = int(duration * 16000)
            x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
            audio = np.interp(x_new, x_old, audio).astype(np.float32)

        result = self._model.transcribe(
            audio,
            language="en",
            task="transcribe",
            temperature=0.0,
            word_timestamps=True,
            condition_on_previous_text=False,
            initial_prompt=config.WHISPER_INITIAL_PROMPT,
            fp16=self.device_config.device == "cuda" if self.device_config else False,
        )

        words: list[WordTiming] = []
        for seg in result.get("segments") or []:
            for w in seg.get("words") or []:
                token = str(w.get("word") or "").strip()
                if not token:
                    continue
                # torch whisper word confidence is not always present
                prob = w.get("probability")
                if prob is None:
                    prob = max(0.0, 1.0 - float(w.get("no_speech_prob") or 0.0))
                words.append(
                    WordTiming(
                        word=token,
                        start=float(w.get("start") or 0.0),
                        end=float(w.get("end") or 0.0),
                        probability=float(prob if prob is not None else 0.85),
                    )
                )

        text = str(result.get("text") or "").strip()
        text = re.sub(r"\s+", " ", text)
        duration = float(len(audio) / 16000.0)
        if words:
            duration = max(duration, words[-1].end)
        return TranscriptResult(
            text=text,
            duration_sec=duration,
            no_speech_prob=0.0 if text else 1.0,
            avg_logprob=-0.5,
            words=words,
        )


transcriber = Transcriber()
