"""docs/tests/docs_completeness.py

Verifica que todos los códigos de error LMN-XXXX presentes en el código fuente
de lumen/ estén documentados en docs/errors.md.

Uso:
    python docs/tests/docs_completeness.py

Salida:
    - Código 0 si todos los códigos están documentados.
    - Código 1 con lista de códigos faltantes si hay alguno sin documentar.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Patrón para detectar códigos de error en archivos .py
ERROR_CODE_PATTERN = re.compile(r'"(LMN-\d{4})"')

# Códigos que son placeholders o genéricos (no requieren entrada en docs)
EXCLUDED_CODES: frozenset[str] = frozenset(
    {
        "LMN-0000",  # Código genérico de fallback en pipeline
        "LMN-0099",  # Código genérico de RuntimeError en interpreter
    }
)


def find_codes_in_source(lumen_root: Path) -> set[str]:
    """Escanea todos los .py en lumen/ y retorna los códigos LMN-XXXX encontrados."""
    codes: set[str] = set()
    for py_file in lumen_root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="replace")
        for match in ERROR_CODE_PATTERN.finditer(text):
            code = match.group(1)
            if code not in EXCLUDED_CODES:
                codes.add(code)
    return codes


def find_codes_in_docs(errors_md: Path) -> set[str]:
    """Lee docs/errors.md y retorna todos los códigos LMN-XXXX mencionados."""
    text = errors_md.read_text(encoding="utf-8", errors="replace")
    # Captura cualquier aparición de LMN-XXXX en el documento
    return set(re.findall(r"LMN-\d{4}", text))


def check_completeness(
    lumen_root: Path | None = None,
    errors_md: Path | None = None,
) -> tuple[set[str], set[str]]:
    """
    Compara los códigos del código fuente con los de la documentación.

    Returns:
        (source_codes, missing_codes)
        - source_codes: todos los códigos encontrados en lumen/
        - missing_codes: códigos en código pero NO en docs/errors.md
    """
    repo_root = Path(__file__).parent.parent.parent

    if lumen_root is None:
        lumen_root = repo_root / "lumen"
    if errors_md is None:
        errors_md = repo_root / "docs" / "errors.md"

    if not lumen_root.is_dir():
        raise FileNotFoundError(f"Directorio lumen/ no encontrado: {lumen_root}")
    if not errors_md.is_file():
        raise FileNotFoundError(f"Archivo docs/errors.md no encontrado: {errors_md}")

    source_codes = find_codes_in_source(lumen_root)
    doc_codes = find_codes_in_docs(errors_md)

    missing_codes = source_codes - doc_codes
    return source_codes, missing_codes


def main() -> int:
    try:
        source_codes, missing_codes = check_completeness()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(f"[INFO] Códigos LMN encontrados en lumen/: {len(source_codes)}")
    print(f"       {sorted(source_codes)}")

    if missing_codes:
        print(
            f"\n[FAIL] {len(missing_codes)} código(s) sin documentar en docs/errors.md:",
            file=sys.stderr,
        )
        for code in sorted(missing_codes):
            print(f"       - {code}", file=sys.stderr)
        return 1

    print("\n[OK] Todos los códigos de error están documentados en docs/errors.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
