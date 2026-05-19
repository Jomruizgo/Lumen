"""Benchmark D.7 — Eficiencia de tokens: Lumen vs Python.

Para cada uno de los 15 ejemplos .lumen en examples/:
  1. Cuenta tokens del source Lumen (tiktoken cl100k_base o word-count proxy).
  2. Lee el equivalente Python en benchmarks/python_equivalents/.
  3. Cuenta tokens del equivalente Python.
  4. Calcula ratio = lumen_tokens / python_tokens.
  5. Imprime tabla y reporte de promedio.
  6. Exit 0 si promedio ≤ threshold (default 0.5), exit 1 si no.

Uso:
    py -m benchmarks.token_efficiency
    py -m benchmarks.token_efficiency --threshold=0.6
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_EXAMPLES_DIR = _REPO_ROOT / "examples"
_PY_EQUIV_DIR = Path(__file__).parent / "python_equivalents"


# ---------------------------------------------------------------------------
# Contador de tokens
# ---------------------------------------------------------------------------

def _make_counter() -> tuple[Callable[[str], int], str]:
    """Retorna (función_cuenta, etiqueta).

    Prefiere tiktoken (cl100k_base); si no está instalado usa word-count
    como proxy: tokens ≈ palabras / 0.75.
    """
    try:
        import tiktoken  # type: ignore[import]
        enc = tiktoken.get_encoding("cl100k_base")

        def _count_tiktoken(source: str) -> int:
            return len(enc.encode(source))

        return _count_tiktoken, "tiktoken cl100k_base"
    except ImportError:
        def _count_words(source: str) -> int:
            words = len(source.split())
            return max(1, round(words / 0.75))

        return _count_words, "word-count / 0.75 (instala tiktoken para mayor precisión)"


# ---------------------------------------------------------------------------
# Carga de archivos
# ---------------------------------------------------------------------------

def _load_pairs() -> list[tuple[str, str, str]]:
    """Retorna lista de (nombre, source_lumen, source_python) para los 15 ejemplos.

    Si un equivalente Python no existe lanza FileNotFoundError.
    """
    lumen_files = sorted(_EXAMPLES_DIR.glob("*.lumen"))
    if not lumen_files:
        raise FileNotFoundError(f"No se encontraron archivos .lumen en {_EXAMPLES_DIR}")

    pairs: list[tuple[str, str, str]] = []
    for lf in lumen_files:
        stem = lf.stem  # e.g. "01_hello"
        py_file = _PY_EQUIV_DIR / f"{stem}.py"
        if not py_file.exists():
            print(
                f"[WARN] Equivalente Python no encontrado: {py_file}. Saltando {lf.name}.",
                file=sys.stderr,
            )
            continue
        lumen_src = lf.read_text(encoding="utf-8")
        py_src = py_file.read_text(encoding="utf-8")
        pairs.append((lf.name, lumen_src, py_src))

    return pairs


# ---------------------------------------------------------------------------
# Tabla de resultados
# ---------------------------------------------------------------------------

def _print_table(
    rows: list[tuple[str, int, int, float]],
    counter_label: str,
    threshold: float,
) -> None:
    col_name = 30
    col_lumen = 10
    col_python = 10
    col_ratio = 12
    header = (
        f"{'Ejemplo':<{col_name}}  {'Lumen':>{col_lumen}}  "
        f"{'Python':>{col_python}}  {'Ratio (Lm/Py)':>{col_ratio}}"
    )
    sep = "-" * len(header)
    print(f"\nD.7 Benchmark — Eficiencia de tokens ({counter_label})")
    print(sep)
    print(header)
    print(sep)
    for name, lumen_t, python_t, ratio in rows:
        flag = " OK" if ratio <= threshold else " !!"
        print(
            f"{name:<{col_name}}  {lumen_t:>{col_lumen},}  "
            f"{python_t:>{col_python},}  {ratio:>{col_ratio}.3f}{flag}"
        )
    print(sep)

    avg_ratio = sum(r for _, _, _, r in rows) / len(rows) if rows else 0.0
    status = "PASS" if avg_ratio <= threshold else "FAIL"
    print(
        f"\nPromedio ratio (Lm/Py): {avg_ratio:.3f}  |  "
        f"Threshold: <= {threshold}  |  {status}"
    )


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark de eficiencia de tokens Lumen vs Python."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        metavar="N",
        help="Ratio máximo aceptable lumen_tokens/python_tokens (default: 0.5).",
    )
    args = parser.parse_args(argv)
    threshold: float = args.threshold

    count_tokens, counter_label = _make_counter()

    try:
        pairs = _load_pairs()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if not pairs:
        print("[ERROR] No hay pares de archivos para comparar.", file=sys.stderr)
        return 1

    rows: list[tuple[str, int, int, float]] = []
    for name, lumen_src, py_src in pairs:
        lt = count_tokens(lumen_src)
        pt = count_tokens(py_src)
        ratio = lt / pt if pt > 0 else 0.0
        rows.append((name, lt, pt, ratio))

    _print_table(rows, counter_label, threshold)

    avg_ratio = sum(r for _, _, _, r in rows) / len(rows) if rows else 0.0
    return 0 if avg_ratio <= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
