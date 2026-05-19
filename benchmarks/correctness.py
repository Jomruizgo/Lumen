"""
Benchmark: tasa de corrección al primer intento.
Valida que programas de ejemplo compilen sin errores.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from lumen.compiler.pipeline import compile_source, CompileError

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


# ---------------------------------------------------------------------------
# Tipos de resultado
# ---------------------------------------------------------------------------

@dataclass
class FileResult:
    path: Path
    passed: bool
    errors: list[CompileError] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class BenchmarkSummary:
    total: int
    passed: int
    failed: int
    results: list[FileResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100) if self.total > 0 else 0.0


# ---------------------------------------------------------------------------
# Ejecución del benchmark
# ---------------------------------------------------------------------------

def run_benchmark(examples_dir: Path = EXAMPLES_DIR) -> BenchmarkSummary:
    """Escanea examples_dir, compila cada .lumen y retorna un resumen."""
    lumen_files = sorted(examples_dir.glob("*.lumen"))
    results: list[FileResult] = []

    for lumen_file in lumen_files:
        source = lumen_file.read_text(encoding="utf-8")
        compile_result = compile_source(source)
        results.append(
            FileResult(
                path=lumen_file,
                passed=compile_result.ok,
                errors=list(compile_result.errors),
            )
        )

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    return BenchmarkSummary(
        total=len(results),
        passed=passed,
        failed=failed,
        results=results,
    )


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

def _print_summary(summary: BenchmarkSummary) -> None:
    col_name = 35
    col_status = 8
    header = f"{'Archivo':<{col_name}}  {'Estado':^{col_status}}  Errores"
    sep = "-" * (col_name + col_status + 30)

    print(f"\nBenchmark de corrección — Lumen compiler\n{sep}")
    print(header)
    print(sep)

    for r in summary.results:
        status = "OK" if r.passed else "FAIL"
        error_summary = ""
        if not r.passed:
            parts = [f"[{e.code}] {e.message}" for e in r.errors[:3]]
            if len(r.errors) > 3:
                parts.append(f"... y {len(r.errors) - 3} más")
            error_summary = " | ".join(parts)
        print(f"{r.name:<{col_name}}  {status:^{col_status}}  {error_summary}")

    print(sep)
    print(
        f"\nTotal: {summary.total}  |  "
        f"Correctos: {summary.passed}  |  "
        f"Fallidos: {summary.failed}  |  "
        f"Tasa de acierto: {summary.pass_rate:.1f}%"
    )

    if summary.failed > 0:
        print("\nDetalle de errores:")
        for r in summary.results:
            if not r.passed:
                print(f"\n  {r.name}:")
                for e in r.errors:
                    print(f"    [{e.code}] línea {e.line}, col {e.col}: {e.message}")

    print()


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    summary = run_benchmark()
    _print_summary(summary)

    if summary.failed > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
