#!/usr/bin/env bash
# Verificación de la librería hotel-booking.
#
# La librería es pura: no hay servidor, ni base de datos, ni servicios que
# iniciar. Este script ejecuta el ejemplo numérico verificado y la suite de
# pruebas (pytest).
#
# Uso:  ./run.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$RAIZ"

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Error: no se encontró el intérprete '$PYTHON'." >&2
    exit 1
fi

echo "== Ejemplo verificado =="
"$PYTHON" - <<'PY'
import sys

sys.path.insert(0, "src")

from datetime import date

from booking import stay_total

print(stay_total(date(2026, 1, 2), date(2026, 1, 4), "double", 2))
PY

echo
echo "== Suite de pruebas =="
if "$PYTHON" -c "import pytest" >/dev/null 2>&1; then
    "$PYTHON" -m pytest -q
else
    echo "pytest no está disponible; se instala el extra de desarrollo 'dev'."
    "$PYTHON" -m pip install --quiet --disable-pip-version-check -e ".[dev]"
    "$PYTHON" -m pytest -q
fi
