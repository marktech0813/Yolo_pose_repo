# Northline — Offline CUDA 11.8 wheel environments

Ship this app to offline Windows/Linux PCs with **Python wheels** (no internet on the target).

## Supported matrix

| OS | Python | Mode | Wheelhouse folder |
|----|--------|------|-------------------|
| Linux x86_64 | **3.10** | **GPU CUDA 11.8** (recommended) | `wheelhouse/linux-cp310-cu118/` |
| Windows amd64 | **3.10** | **GPU CUDA 11.8** (recommended) | `wheelhouse/windows-cp310-cu118/` |
| Linux x86_64 | 3.13 | CPU only | `wheelhouse/linux-cp313-cpu/` |
| Windows amd64 | 3.13 | CPU only | `wheelhouse/windows-cp313-cpu/` |

**Why 3.10 for GPU?** Official `torch==2.1.2+cu118` wheels exist for Win+Linux on cp310. CUDA 11.8 wheels are not published for Python 3.13.

## What runs on the GPU

1. **Linux:** `faster-whisper` via **CTranslate2 CUDA** when a GPU is visible; NVIDIA cu11 pip libs are bundled in the wheelhouse.
2. **Windows:** If CTranslate2 reports 0 CUDA devices, Northline uses **PyTorch cu118 + openai-whisper** automatically.
3. Override with env:
   - `NORTHLINE_DEVICE=cuda` | `cpu` | `auto` (default)
   - `NORTHLINE_COMPUTE_TYPE=float16` (GPU) / `int8` (CPU)

## One-time online packaging PC

Requirements on the packaging machine: Python 3.10, internet, Java not required for wheel download.

```bash
cd chat_analysis_app
python3.10 -m venv .packvenv && source .packvenv/bin/activate   # or Windows venv
pip install -U pip
python scripts/download_wheelhouse.py --target linux310-gpu
python scripts/download_wheelhouse.py --target windows310-gpu
# optional CPU 3.13 houses:
# python scripts/download_wheelhouse.py --target linux313-cpu
# python scripts/download_wheelhouse.py --target windows313-cpu
python scripts/download_assets.py   # Whisper + LanguageTool + fonts → models/
```

This repo already includes built GPU houses under `wheelhouse/` when packaged (~4GB each):

- `wheelhouse/linux-cp310-cu118/`
- `wheelhouse/windows-cp310-cu118/`

Copy to the offline PC:

- whole `chat_analysis_app/` including `wheelhouse/` and `models/`
- (optional) exclude `.venv/` / `.packvenv/`

If you cloned the GitHub copy, `wheelhouse/` and `models/` are split into 50 MB zip parts under `offline_parts/`. Rebuild them with:

```bash
chmod +x scripts/restore_offline_bundles.sh
./scripts/restore_offline_bundles.sh
```

## Offline install — Linux

```bash
# GPU Python 3.10 + CUDA 11.8 driver on the machine
sudo apt-get install -y openjdk-17-jre-headless   # if not present
chmod +x scripts/install_offline.sh scripts/run.sh
./scripts/install_offline.sh gpu
./scripts/run.sh
```

Open `https://<host>:8443` (accept self-signed cert).

CPU / Python 3.13:

```bash
./scripts/install_offline.sh cpu313
```

## Offline install — Windows

1. Install **Python 3.10** (64-bit) and **Java 17+** JRE.
2. Install an NVIDIA driver that supports **CUDA 11.8** (driver ≥ 450.80; Game Ready/Studio is fine).
3. PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_offline.ps1 -Mode gpu
.\scripts\run.ps1
```

Open `https://127.0.0.1:8443`.

## Verify GPU

```bash
# Linux
source .venv/bin/activate
python -c "import ctranslate2,torch; print('ct2',ctranslate2.get_cuda_device_count()); print('torch',torch.cuda.is_available(), torch.version.cuda)"
curl -sk https://127.0.0.1:8443/api/health
# expect "cuda": true when GPU path is active
```

## Notes

- Target PCs stay offline after wheels + `models/` are copied.
- LanguageTool still needs a local **Java 17+** runtime (not a pip wheel).
- Mic in the browser requires **HTTPS** (or localhost). `scripts/run.sh` / `run.ps1` serve HTTPS on **8443**.
- First GPU load can take longer while kernels initialize; keep `workers=1`.
