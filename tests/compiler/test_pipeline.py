"""Tests para el pipeline completo del compilador Lumen."""

from __future__ import annotations

import pytest

from lumen.compiler.pipeline import compile_source, CompilerPipeline


HELLO = """\
@lumen 1.0

print "Hello, World"
"""

SAFE_PROGRAM = """\
@lumen 1.0
use sensitive.transfer

action pay(supplier, amount):
  reversible: 24h
  execute:
    sensitive.transfer(from="company", to=supplier, amount=amount)
"""

BAD_NO_VERSION = 'print "hello"'

BAD_NO_USE = """\
@lumen 1.0

comm.email.read(since="yesterday")
"""

BAD_TYPE_MISMATCH = """\
@lumen 1.0

usd = $100 USD
eur = €50 EUR
total = usd + eur
"""

FLOW_PROGRAM = """\
@lumen 1.0
use comm.email

agent email_monitor:
  watch: comm.email.inbox
  on new_email:
    print "New email received"
"""


def test_compile_hello_ok():
    result = compile_source(HELLO)
    assert result.ok
    assert result.program is not None
    assert result.errors == []


def test_compile_returns_compiled_program():
    result = compile_source(HELLO)
    assert result.program is not None
    assert hasattr(result.program, "mode")
    assert hasattr(result.program, "instrumented")


def test_mode_fast_inferred():
    result = compile_source(HELLO)
    assert result.ok
    assert result.program.mode == "fast"


def test_mode_safe_inferred():
    result = compile_source(SAFE_PROGRAM)
    assert result.ok
    assert result.program.mode == "safe"


def test_mode_flow_inferred():
    result = compile_source(FLOW_PROGRAM)
    assert result.ok
    assert result.program.mode == "flow"


def test_ast_accessible_via_instrumented():
    result = compile_source(HELLO)
    assert result.ok
    ast = result.program.instrumented.resolved.typed.ast
    assert ast is not None
    assert hasattr(ast, "top_levels")


def test_missing_version_error():
    result = compile_source(BAD_NO_VERSION)
    assert not result.ok
    codes = [e.code for e in result.errors]
    assert "LMN-0100" in codes


def test_missing_use_error():
    result = compile_source(BAD_NO_USE)
    assert not result.ok
    codes = [e.code for e in result.errors]
    assert "LMN-0001" in codes


def test_source_hash_format():
    result = compile_source(HELLO)
    assert result.ok
    assert result.program.source_hash.startswith("sha256:")
    assert len(result.program.source_hash) == 71  # "sha256:" + 64 hex chars


def test_multiple_errors_collected():
    bad = """\
@lumen 1.0

comm.email.read()
sensitive.transfer(to="x", amount=100)
"""
    result = compile_source(bad)
    assert not result.ok
    assert len(result.errors) >= 2


def test_check_method_returns_errors():
    pipeline = CompilerPipeline()
    errors = pipeline.check(BAD_NO_VERSION)
    assert len(errors) > 0
    assert errors[0].code == "LMN-0100"


def test_check_method_returns_empty_on_valid():
    pipeline = CompilerPipeline()
    errors = pipeline.check(HELLO)
    assert errors == []


def test_compile_empty_program():
    empty = "@lumen 1.0\n"
    result = compile_source(empty)
    assert result.ok


def test_program_source_preserved():
    result = compile_source(HELLO)
    assert result.ok
    assert result.program.source == HELLO
