#!/usr/bin/env bash
# Offline install on Linux (Python 3.10 + CUDA 11.8 recommended).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE="${1:-gpu}"   # gpu | cpu313
PY="${PYTHON:-python3.10}"

if [[ "$MODE" == "cpu313" ]]; then
  PY="${PYTHON:-python3.13}"
  WHEEL="$ROOT/wheelhouse/linux-cp313-cpu"
  REQ="$ROOT/requirements/cpu-py313.txt"
else
  WHEEL="$ROOT/wheelhouse/linux-cp310-cu118"
  REQ="$ROOT/requirements/gpu-cu118.txt"
fi

if [[ ! -d "$WHEEL" ]] || ! ls "$WHEEL"/*.whl >/dev/null 2>&1; then
  echo "ERROR: missing wheels in $WHEEL"
  echo "On an online PC run: python scripts/download_wheelhouse.py"
  exit 1
fi

if ! command -v java >/dev/null; then
  echo "ERROR: Java 17+ required for LanguageTool (openjdk-17-jre-headless)"
  exit 1
fi

# Flatten nested -r requirements for offline pip
FLAT="$(mktemp)"
trap 'rm -f "$FLAT"' EXIT
while IFS= read -r line; do
  s="$(echo "$line" | sed 's/#.*//;s/[[:space:]]*$//')"
  [[ -z "$s" ]] && continue
  if [[ "$s" == -r* ]]; then
    nested="$(echo "$s" | awk '{print $2}')"
    sed 's/#.*//' "$ROOT/requirements/$nested" | sed '/^[[:space:]]*$/d' | sed '/^-r /d' >>"$FLAT"
  else
    echo "$s" >>"$FLAT"
  fi
done <"$REQ"

"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install --no-index --find-links="$WHEEL" -r "$FLAT"

python - <<'PY'
import ctranslate2
print("ctranslate2", ctranslate2.__version__, "cuda_devices", ctranslate2.get_cuda_device_count())
try:
    import torch
    print("torch", torch.__version__, "cuda", torch.cuda.is_available())
except Exception as e:
    print("torch not available:", e)
PY

echo
echo "Installed from $WHEEL"
echo "Set NORTHLINE_DEVICE=cuda (or leave auto). Run: ./scripts/run.sh"
echo "Need models/: run scripts/download_assets.py once online, then copy models/ offline."
