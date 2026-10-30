#!/usr/bin/env bash
# Rebuild wheelhouse/ and models/ from 50MB split zips in offline_parts/.
# Run from anywhere; paths are relative to the app root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PARTS="$ROOT/offline_parts"
cd "$ROOT"

restore_one() {
  local name="$1"
  local split="$PARTS/${name}.zip"
  if [[ ! -f "$split" ]]; then
    echo "Missing $split"
    exit 1
  fi
  echo "Joining $name split archive..."
  local full
  full="$(mktemp -d)/${name}-full.zip"
  zip -s 0 "$split" --out "$full"
  echo "Extracting $name..."
  unzip -q -o "$full" -d "$ROOT"
  rm -f "$full"
  rmdir "$(dirname "$full")" 2>/dev/null || true
}

restore_one wheelhouse
restore_one models
echo "Restored wheelhouse/ and models/."
echo "Next: ./scripts/install_offline.sh gpu   then   ./scripts/run.sh"
