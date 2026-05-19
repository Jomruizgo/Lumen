"""Tests de integración: compilador → intérprete round-trip."""

from __future__ import annotations

import pytest

from lumen.compiler.pipeline import compile_source
from lumen.runtime.interpreter import Interpreter
from lumen.stdlib.base import ExecutionContext


async def _run(source: str) -> tuple[bool, str]:
    """Compile + run, return (success, output)."""
    result = compile_source(source)
    if not result.ok:
        return False, "; ".join(e.message for e in result.errors)
    ctx = ExecutionContext(mode=result.program.mode)
    interp = Interpreter(context=ctx)
    exec_result = await interp.run(result.program)
    return exec_result.success, exec_result.output or ""


async def test_hello_world_full_pipeline():
    ok, output = await _run('@lumen 1.0\nprint "Hello, World"\n')
    assert ok
    assert "Hello, World" in output


async def test_arithmetic_assignment():
    ok, output = await _run(
        "@lumen 1.0\n"
        "x = 3 + 4\n"
        "print x\n"
    )
    assert ok
    assert "7" in output


async def test_string_concat():
    ok, output = await _run(
        '@lumen 1.0\n'
        'a = "Hello"\n'
        'b = ", World"\n'
        'print a\n'
    )
    assert ok
    assert "Hello" in output


async def test_boolean_literal():
    ok, output = await _run(
        "@lumen 1.0\n"
        "x = true\n"
        "print x\n"
    )
    assert ok
    assert "True" in output


async def test_compile_and_check_mode_fast():
    result = compile_source("@lumen 1.0\nprint \"hi\"\n")
    assert result.ok
    assert result.program.mode == "fast"


async def test_compile_and_check_mode_safe():
    source = (
        "@lumen 1.0\n"
        "use sensitive.transfer\n"
        "action pay(x, amount):\n"
        "  reversible: 24h\n"
        "  execute:\n"
        "    sensitive.transfer(to=x, amount=amount)\n"
    )
    result = compile_source(source)
    assert result.ok
    assert result.program.mode == "safe"


async def test_lmn_0100_missing_version():
    result = compile_source('print "hello"\n')
    assert not result.ok
    assert any(e.code == "LMN-0100" for e in result.errors)


async def test_lmn_0001_undeclared_capability():
    result = compile_source("@lumen 1.0\ncomm.email.read(since=\"yesterday\")\n")
    assert not result.ok
    assert any(e.code == "LMN-0001" for e in result.errors)


async def test_multiple_prints():
    ok, output = await _run(
        '@lumen 1.0\nprint "line1"\nprint "line2"\nprint "line3"\n'
    )
    assert ok
    assert "line1" in output
    assert "line2" in output
    assert "line3" in output


async def test_dry_run_shows_plan():
    from lumen.tooling.dryrun import dry_run
    source = (
        "@lumen 1.0\n"
        "use sensitive.transfer\n"
        "action pay(x):\n"
        "  reversible: 24h\n"
        "  execute:\n"
        "    sensitive.transfer(to=x)\n"
    )
    plan = dry_run(source)
    assert plan.mode in ("fast", "safe", "flow")
    assert len(plan.steps) > 0
    text = plan.to_text()
    assert "DRY-RUN" in text


async def test_explain_returns_capabilities():
    from lumen.tooling.explain import explain
    source = (
        "@lumen 1.0\n"
        "use comm.email\n"
        "print \"hi\"\n"
    )
    expl = explain(source)
    assert "comm.email" in expl.capabilities
    text = expl.to_text()
    assert "comm.email" in text


async def test_source_hash_deterministic():
    source = "@lumen 1.0\nprint \"hi\"\n"
    r1 = compile_source(source)
    r2 = compile_source(source)
    assert r1.ok and r2.ok
    assert r1.program.source_hash == r2.program.source_hash
