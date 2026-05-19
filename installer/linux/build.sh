#!/usr/bin/env bash
# build.sh — Genera binario lumen standalone en Linux usando PyInstaller
# Uso: bash installer/linux/build.sh  (desde la raíz del proyecto)
#      o:  ./build.sh  (desde installer/linux/)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "[lumen] Ejecutando build.py desde $SCRIPT_DIR..."
python3 "$SCRIPT_DIR/build.py"

BINARY="$SCRIPT_DIR/dist/lumen"
if [[ -f "$BINARY" ]]; then
    echo "[OK] Binario disponible en: $BINARY"
else
    echo "[ERROR] No se encontró el binario en $BINARY" >&2
    exit 1
fi
