"""Tests E2E: compila y ejecuta los 15 ejemplos."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from lumen.compiler.pipeline import compile_source
from lumen.runtime.interpreter import Interpreter
from lumen.tooling.dryrun import dry_run

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"

_LUMEN_FILES = sorted(EXAMPLES_DIR.glob("*.lumen"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(name: str) -> str:
    return (EXAMPLES_DIR / name).read_text(encoding="utf-8")


def _run_interpreter(source: str) -> "ExecutionResult":  # type: ignore[name-defined]
    from lumen.runtime.interpreter import Interpreter

    compiled = compile_source(source)
    assert compiled.ok, f"La compilación falló: {compiled.errors}"
    interpreter = Interpreter()
    return asyncio.run(interpreter.run(compiled.program))


# ---------------------------------------------------------------------------
# 1. Todos los ejemplos compilan
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lumen_file", _LUMEN_FILES, ids=[f.name for f in _LUMEN_FILES])
def test_all_examples_compile(lumen_file: Path) -> None:
    """Cada archivo .lumen en examples/ debe compilar sin errores."""
    source = lumen_file.read_text(encoding="utf-8")
    result = compile_source(source)
    assert result.ok, (
        f"{lumen_file.name} falló al compilar: "
        + "; ".join(f"[{e.code}] {e.message}" for e in result.errors)
    )


# ---------------------------------------------------------------------------
# 2. Hello World produce salida con "Hello"
# ---------------------------------------------------------------------------

def test_hello_world_output() -> None:
    """01_hello.lumen debe producir una salida que contenga 'Hello'."""
    source = _read("01_hello.lumen")
    exec_result = _run_interpreter(source)
    assert exec_result.success, f"La ejecución falló: {exec_result.error}"
    output = str(exec_result.output or "")
    assert "Hello" in output, f"Salida esperada contiene 'Hello', obtenida: {output!r}"


# ---------------------------------------------------------------------------
# 3. Inferencia de modo: fast
# ---------------------------------------------------------------------------

def test_mode_inference_fast() -> None:
    """01_hello.lumen (sin capabilities especiales) debe inferirse como modo 'fast'."""
    source = _read("01_hello.lumen")
    result = compile_source(source)
    assert result.ok, f"Compilación falló: {result.errors}"
    assert result.program is not None
    assert result.program.mode == "fast", (
        f"Modo esperado 'fast', obtenido '{result.program.mode}'"
    )


# ---------------------------------------------------------------------------
# 4. Inferencia de modo: safe
# ---------------------------------------------------------------------------

def test_mode_inference_safe() -> None:
    """14_constants.lumen (usa sensitive.transfer) debe inferirse como modo 'safe'."""
    source = _read("14_constants.lumen")
    result = compile_source(source)
    assert result.ok, f"Compilación falló: {result.errors}"
    assert result.program is not None
    assert result.program.mode == "safe", (
        f"Modo esperado 'safe', obtenido '{result.program.mode}'"
    )


# ---------------------------------------------------------------------------
# 5. Inferencia de modo: flow
# ---------------------------------------------------------------------------

_FLOW_SOURCE = """\
@lumen 1.0
use comm.notify

agent simple_agent:
  on tick:
    comm.notify("hello")

  config:
    escalation: cli
"""


def test_mode_inference_flow() -> None:
    """Un programa con AgentDecl debe inferirse como modo 'flow'."""
    result = compile_source(_FLOW_SOURCE)
    assert result.ok, f"Compilación falló: {result.errors}"
    assert result.program is not None
    assert result.program.mode == "flow", (
        f"Modo esperado 'flow', obtenido '{result.program.mode}'"
    )


# ---------------------------------------------------------------------------
# 6. Rechaza llamada a capability sin 'use'
# ---------------------------------------------------------------------------

def test_compiler_rejects_missing_use() -> None:
    """Un programa que llama comm.email sin declarar 'use comm.email' debe fallar con LMN-0001."""
    source = """\
@lumen 1.0

emails = read.email(since="yesterday")
"""
    result = compile_source(source)
    assert not result.ok, "Se esperaba error de compilación por capability no declarada"
    codes = [e.code for e in result.errors]
    assert "LMN-0001" in codes, (
        f"Se esperaba error LMN-0001 (capability no declarada), obtenidos: {codes}"
    )


# ---------------------------------------------------------------------------
# 7. Rechaza type mismatch (Money USD + Money EUR)
# ---------------------------------------------------------------------------

def test_compiler_rejects_type_mismatch() -> None:
    """Sumar $100 USD + €50 EUR debe producir error LMN-0030."""
    source = """\
@lumen 1.0

total = $100 USD + €50 EUR
"""
    result = compile_source(source)
    assert not result.ok, "Se esperaba error de compilación por tipo incompatible"
    codes = [e.code for e in result.errors]
    assert "LMN-0030" in codes, (
        f"Se esperaba error LMN-0030 (type mismatch), obtenidos: {codes}"
    )


# ---------------------------------------------------------------------------
# 8. Rechaza programa sin directiva @lumen
# ---------------------------------------------------------------------------

def test_compiler_rejects_missing_version() -> None:
    """Un programa sin directiva '@lumen' debe fallar con LMN-0100."""
    source = 'print "hello"\n'
    result = compile_source(source)
    assert not result.ok, "Se esperaba error de compilación por falta de @lumen"
    codes = [e.code for e in result.errors]
    assert "LMN-0100" in codes, (
        f"Se esperaba error LMN-0100 (versión faltante), obtenidos: {codes}"
    )


# ---------------------------------------------------------------------------
# 9. Dry-run muestra plan con pasos
# ---------------------------------------------------------------------------

def test_dry_run_shows_plan() -> None:
    """dry_run sobre 05_pay_supplier/04_payment debe retornar un DryRunPlan con pasos."""
    source = _read("04_payment.lumen")
    plan = dry_run(source)
    assert plan is not None, "dry_run debe retornar un DryRunPlan"
    assert len(plan.steps) > 0, (
        f"El plan debe tener al menos un paso; obtenidos: {plan.steps}"
    )
