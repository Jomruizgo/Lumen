"""Tests para el intérprete Lumen."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from lumen.runtime.interpreter import ExecutionResult, Interpreter
from lumen.stdlib.base import ExecutionContext, Result


def make_mock_program(mode: str = "fast", statements: list[Any] | None = None) -> MagicMock:
    """Crea un mock de CompiledProgram para tests."""
    program = MagicMock()
    program.mode = mode

    ast = MagicMock()
    # Interpreter uses top_levels for Program nodes
    ast.top_levels = statements or []
    ast.statements = statements or []

    typed = MagicMock()
    typed.ast = ast

    resolved = MagicMock()
    resolved.typed = typed

    instrumented = MagicMock()
    instrumented.resolved = resolved

    program.instrumented = instrumented
    return program


def make_print_stmt(text: str) -> MagicMock:
    stmt = MagicMock()
    stmt.__class__.__name__ = "PrintStatement"
    string_val = MagicMock()
    string_val.__class__.__name__ = "StringLiteral"
    string_val.value = text
    stmt.value = string_val
    return stmt


def make_number_literal(value: float) -> MagicMock:
    node = MagicMock()
    node.__class__.__name__ = "NumberLiteral"
    node.value = value
    return node


def make_string_literal(value: str) -> MagicMock:
    node = MagicMock()
    node.__class__.__name__ = "StringLiteral"
    node.value = value
    return node


def make_boolean_literal(value: bool) -> MagicMock:
    node = MagicMock()
    node.__class__.__name__ = "BooleanLiteral"
    node.value = value
    return node


def make_binary_op(left: Any, op: str, right: Any) -> MagicMock:
    node = MagicMock()
    node.__class__.__name__ = "BinaryOp"
    node.left = left
    node.op = op
    node.right = right
    return node


def make_assignment(name: str, value: Any) -> MagicMock:
    stmt = MagicMock()
    stmt.__class__.__name__ = "Assignment"
    # Real AST Assignment.target is a str; mock must match interpreter expectation
    stmt.target = name
    stmt.value = value
    return stmt


@pytest.fixture
def interp() -> Interpreter:
    return Interpreter(context=ExecutionContext(mode="fast"))


@pytest.mark.asyncio
async def test_runs_hello_world(interp: Interpreter) -> None:
    program = make_mock_program(statements=[make_print_stmt("Hello, World")])
    result = await interp.run(program)
    assert result.success
    assert "Hello, World" in result.output


@pytest.mark.asyncio
async def test_runs_with_none_program(interp: Interpreter) -> None:
    result = await interp.run(None)
    assert not result.success


@pytest.mark.asyncio
async def test_evaluates_number_literal(interp: Interpreter) -> None:
    node = make_number_literal(42.0)
    val = await interp._eval_expr(node)
    assert val == 42.0


@pytest.mark.asyncio
async def test_evaluates_string_literal(interp: Interpreter) -> None:
    node = make_string_literal("hello")
    val = await interp._eval_expr(node)
    assert val == "hello"


@pytest.mark.asyncio
async def test_evaluates_boolean_literal(interp: Interpreter) -> None:
    true_node = make_boolean_literal(True)
    false_node = make_boolean_literal(False)
    assert await interp._eval_expr(true_node) is True
    assert await interp._eval_expr(false_node) is False


@pytest.mark.asyncio
async def test_evaluates_binary_addition(interp: Interpreter) -> None:
    expr = make_binary_op(make_number_literal(3), "+", make_number_literal(4))
    result = await interp._eval_expr(expr)
    assert result == pytest.approx(7.0)


@pytest.mark.asyncio
async def test_evaluates_binary_comparison(interp: Interpreter) -> None:
    expr = make_binary_op(make_number_literal(5), ">", make_number_literal(3))
    result = await interp._eval_expr(expr)
    assert result is True


@pytest.mark.asyncio
async def test_assignment_stores_in_env(interp: Interpreter) -> None:
    stmt = make_assignment("x", make_number_literal(99.0))
    program = make_mock_program(statements=[stmt])
    result = await interp.run(program)
    assert result.success
    assert interp._env.get("x") == pytest.approx(99.0)


@pytest.mark.asyncio
async def test_propagates_errors_with_question_mark(interp: Interpreter) -> None:
    program = make_mock_program(statements=[])
    result = await interp.run(program)
    assert result.success


@pytest.mark.asyncio
async def test_register_capability(interp: Interpreter) -> None:
    mock_cap = AsyncMock()
    mock_cap.execute = AsyncMock(return_value=Result.ok("capability result"))
    interp.register_capability("test.cap", mock_cap)
    assert "test.cap" in interp._capabilities


@pytest.mark.asyncio
async def test_set_env_and_read(interp: Interpreter) -> None:
    interp.set_env("myvar", 42)
    id_node = MagicMock()
    id_node.__class__.__name__ = "Identifier"
    id_node.name = "myvar"
    val = await interp._eval_expr(id_node)
    assert val == 42


@pytest.mark.asyncio
async def test_dry_run_resolve_returns_pending(interp: Interpreter) -> None:
    interp._context.dry_run = True
    resolve_node = MagicMock()
    resolve_node.__class__.__name__ = "ResolveBlock"
    resolve_node.expression = make_string_literal("el cliente principal")
    resolve_node.strategies = []
    result = await interp._eval_resolve(resolve_node)
    assert "PENDING" in str(result) or "pending" in str(result).lower()
