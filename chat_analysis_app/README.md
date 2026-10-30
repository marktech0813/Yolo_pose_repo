# Northline

Offline English speech coach. Speak into the mic; Northline **recognizes your English first**, shows the sentence it heard, then marks each word as correct or wrong for **grammar, spelling, native accent, fillers, and fluency** — all on your machine (no internet after setup).

## GPU / offline wheels (Linux + Windows)

For **CUDA 11.8** GPU installs and portable **Python wheelhouses** (Python **3.10** recommended; **3.13** CPU), see **[OFFLINE_GPU.md](OFFLINE_GPU.md)**.

Quick packaging (online PC once):

```bash
python3.10 -m pip install -U pip
python scripts/download_wheelhouse.py --target all
python scripts/download_assets.py
```

Then copy `wheelhouse/` + `models/` + the app to the offline PC and run `scripts/install_offline.sh` (Linux) or `scripts/install_offline.ps1` (Windows).

## Requirements

- Python **3.10** (GPU cu118) or 3.12/3.13 (CPU)
- Java **17+** (LanguageTool local server), e.g. `openjdk-17-jre-headless`
- Optional: NVIDIA driver for CUDA 11.8
- Mic access in the browser (HTTPS or localhost)
- Disk space for models + wheelhouse (several GB with cu118)

## Setup (once, while online)

```bash
cd chat_analysis_app
sudo apt-get install -y openjdk-17-jre-headless   # if needed
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_assets.py
```

`download_assets.py` checks Java ≥ 17, then downloads:

- faster-whisper `small.en` (CPU/GPU)
- LanguageTool (local jar)
- UI fonts (Syne, Literata, Figtree)

## Run (offline)

Browsers only allow the microphone on **HTTPS** or **localhost**.

```bash
cd chat_analysis_app
chmod +x scripts/run.sh
./scripts/run.sh
```

- **App (use this):** `https://<VPS-IP>:8443` — accept the self-signed certificate warning once, then allow the mic
- **Shortcut:** `http://<VPS-IP>:8000` redirects to the HTTPS app

## API

- `GET /api/health` — model readiness
- `POST /api/analyze` — multipart with exactly one of `audio` (16 kHz mono 16-bit WAV) or `text`

## Tests

```bash
source .venv/bin/activate
pytest -q
```

## Limitations

- **English / en-US only.** British spellings may be flagged. Non-English speech is forced into English-like text.
- **Accent alerts** use offline ASR word confidence (not a separate phoneme scorer). Low confidence on a content word is treated as not fully native / unclear. Noise and rare names can raise the same flag.
- The UI always shows the **recognized sentence first**, with green = correct and colored marks for grammar / spelling / accent / fillers.
- Grammar/spelling are judged on the **transcript**. Misheard words can produce wrong corrections; overlap with a spelling hit is reported as “I may have misheard.”
- Replies are **templates**, not a generative tutor.
- Fillers are a **closed list** (`um`, `uh`, `you know`, …). Discourse uses of `like` / `so` are ignored.
- CPU int8 + `beam_size=1` favors latency over accuracy — a few seconds per utterance, one at a time.
- Java 17+ required once. Nothing is uploaded; the thread lives in `sessionStorage` only.

## Design notes

Brand **Northline**. Analysis stays local: browser sends WAV/text to FastAPI; Whisper + LanguageTool never call the public cloud after assets are downloaded.
