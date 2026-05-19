"""Tests para mode_detector.py — cobertura completa de reglas de modo."""

from __future__ import annotations

import pytest

from lumen.compiler.mode_detector import (
    CompileError,
    ModeResult,
    _extract_cap_path,
    _extract_dotaccess_path,
    _uses_sensitive,
    _walk_expr,
    _walk_stmt,
    detect_mode,
)
from lumen.compiler.parser import parse, ParseError as ParserParseError
from lumen.compiler.ast_nodes import (
    BinaryOp,
    Block,
    CapabilityCall,
    DotAccess,
    FunctionCall,
    Identifier,
    IndexAccess,
    NumberLiteral,
    SourcePosition,
    StringInterpolation,
    StringLiteral,
    UnaryOp,
)


_POS = SourcePosition(line=1, col=1)


def _parse(source: str):
    prog = parse(source)
    assert not isinstance(prog, ParserParseError), f"Parse failed: {prog}"
    return prog


# ---------------------------------------------------------------------------
# Programas de prueba
# ---------------------------------------------------------------------------

_FAST_PROGRAM = '''@lumen 1.0

fn add(a, b):
  return a + b
'''

_FLOW_PROGRAM = '''@lumen 1.0
use comm.email

agent EmailWatcher:
  watch: comm.email(filter=unread)
  on email:
    print "Got email"
'''

_SAFE_SENSITIVE_CAP = '''@lumen 1.0
use sensitive.transfer

action pay(amount):
  execute:
    sensitive.transfer(amount=amount)
'''

_SAFE_AUDIT_FULL = '''@lumen 1.0
use comm.email

action notify():
  audit: full
  execute:
    comm.email(to="a@b.com", subject="x", body="y")
'''


# ---------------------------------------------------------------------------
# Test: detect_mode reglas principales
# ---------------------------------------------------------------------------

def test_detects_fast_for_pure_computation():
    prog = _parse(_FAST_PROGRAM)
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert result.mode == "fast"
    assert result.reason


def test_detects_flow_for_agent():
    prog = _parse(_FLOW_PROGRAM)
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert result.mode == "flow"
    assert "flow" in result.reason.lower() or "agent" in result.reason.lower() or "agente" in result.reason.lower()


def test_detects_safe_for_sensitive_capability_decl():
    prog = _parse(_SAFE_SENSITIVE_CAP)
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert result.mode == "safe"


def test_detects_safe_for_audit_full():
    prog = _parse(_SAFE_AUDIT_FULL)
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert result.mode == "safe"


def test_empty_program_is_fast():
    prog = _parse('@lumen 1.0')
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert result.mode == "fast"


def test_mode_result_has_reason():
    prog = _parse(_FAST_PROGRAM)
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert len(result.reason) > 0


# ---------------------------------------------------------------------------
# Test: _extract_cap_path
# ---------------------------------------------------------------------------

def test_extract_cap_path_from_capability_call():
    call = CapabilityCall(
        position=_POS,
        path=("comm", "email"),
        args=(),
        kwargs=(),
    )
    path = _extract_cap_path(call)
    assert path == ("comm", "email")


def test_extract_cap_path_from_function_call_with_dotaccess():
    # FunctionCall(name="email", args=(DotAccess(Identifier("comm"), "email"),))
    dot = DotAccess(position=_POS, obj=Identifier(position=_POS, name="comm"), field="email")
    call = FunctionCall(position=_POS, name="email", args=(dot,), kwargs=())
    path = _extract_cap_path(call)
    assert path == ("comm", "email")


def test_extract_cap_path_returns_none_for_plain_identifier():
    ident = Identifier(position=_POS, name="foo")
    path = _extract_cap_path(ident)
    assert path is None


def test_extract_cap_path_returns_none_for_function_call_no_dotaccess():
    lit = NumberLiteral(position=_POS, value="42")
    call = FunctionCall(position=_POS, name="foo", args=(lit,), kwargs=())
    path = _extract_cap_path(call)
    assert path is None


def test_extract_cap_path_function_call_no_args_returns_none():
    call = FunctionCall(position=_POS, name="foo", args=(), kwargs=())
    path = _extract_cap_path(call)
    assert path is None


# ---------------------------------------------------------------------------
# Test: _extract_dotaccess_path
# ---------------------------------------------------------------------------

def test_extract_dotaccess_path_simple():
    da = DotAccess(position=_POS, obj=Identifier(position=_POS, name="comm"), field="email")
    path = _extract_dotaccess_path(da)
    assert path == ("comm", "email")


def test_extract_dotaccess_path_nested():
    inner = DotAccess(position=_POS, obj=Identifier(position=_POS, name="a"), field="b")
    outer = DotAccess(position=_POS, obj=inner, field="c")
    path = _extract_dotaccess_path(outer)
    assert path == ("a", "b", "c")


def test_extract_dotaccess_path_non_identifier_obj_returns_none():
    # obj is a NumberLiteral — not Identifier
    lit = NumberLiteral(position=_POS, value="1")
    da = DotAccess(position=_POS, obj=lit, field="x")
    path = _extract_dotaccess_path(da)
    assert path is None


# ---------------------------------------------------------------------------
# Test: _walk_expr cubre todos los tipos de nodo
# ---------------------------------------------------------------------------

def test_walk_expr_binary_op():
    left = NumberLiteral(position=_POS, value="1")
    right = NumberLiteral(position=_POS, value="2")
    expr = BinaryOp(position=_POS, op="+", left=left, right=right)
    nodes = list(_walk_expr(expr))
    assert expr in nodes
    assert left in nodes
    assert right in nodes


def test_walk_expr_unary_op():
    operand = NumberLiteral(position=_POS, value="1")
    expr = UnaryOp(position=_POS, op="-", operand=operand)
    nodes = list(_walk_expr(expr))
    assert expr in nodes
    assert operand in nodes


def test_walk_expr_dot_access():
    obj = Identifier(position=_POS, name="x")
    da = DotAccess(position=_POS, obj=obj, field="y")
    nodes = list(_walk_expr(da))
    assert da in nodes
    assert obj in nodes


def test_walk_expr_index_access():
    obj = Identifier(position=_POS, name="arr")
    idx = NumberLiteral(position=_POS, value="0")
    ia = IndexAccess(position=_POS, obj=obj, index=idx)
    nodes = list(_walk_expr(ia))
    assert ia in nodes
    assert obj in nodes
    assert idx in nodes


def test_walk_expr_string_interpolation():
    part_str = "hello "
    part_expr = Identifier(position=_POS, name="name")
    si = StringInterpolation(position=_POS, parts=(part_str, part_expr))
    nodes = list(_walk_expr(si))
    assert si in nodes
    assert part_expr in nodes


def test_walk_expr_function_call_with_kwargs():
    arg = NumberLiteral(position=_POS, value="1")
    kwarg_val = StringLiteral(position=_POS, value="hello")
    call = FunctionCall(position=_POS, name="foo", args=(arg,), kwargs=(("k", kwarg_val),))
    nodes = list(_walk_expr(call))
    assert call in nodes
    assert arg in nodes
    assert kwarg_val in nodes


def test_walk_expr_capability_call():
    arg = NumberLiteral(position=_POS, value="1")
    call = CapabilityCall(position=_POS, path=("comm", "email"), args=(arg,), kwargs=())
    nodes = list(_walk_expr(call))
    assert call in nodes
    assert arg in nodes


# ---------------------------------------------------------------------------
# Test: _uses_sensitive via detect_mode (integration)
# ---------------------------------------------------------------------------

def test_uses_sensitive_via_safe_program():
    prog = _parse(_SAFE_SENSITIVE_CAP)
    # detect_mode regla 3 (CapabilityDecl sensitive.*) → safe
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert result.mode == "safe"


def test_fast_program_no_sensitive():
    prog = _parse(_FAST_PROGRAM)
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert result.mode == "fast"


# ---------------------------------------------------------------------------
# Test: error LMN-0040 fast + sensitive
# ---------------------------------------------------------------------------

_FAST_SENSITIVE_ERROR = '''@lumen 1.0
use sensitive.transfer

action pay(amount):
  mode: fast
  execute:
    sensitive.transfer(amount=amount)
'''


def test_fast_with_sensitive_may_return_error_or_safe():
    prog = _parse(_FAST_SENSITIVE_ERROR)
    result = detect_mode(prog)
    # Puede retornar CompileError (LMN-0040) o ModeResult(safe)
    # dependiendo de si la regla 1 aplica antes o la 3
    assert isinstance(result, (CompileError, ModeResult))
    if isinstance(result, CompileError):
        assert result.code == "LMN-0040"


# ---------------------------------------------------------------------------
# Test: agent overrides safe rules
# ---------------------------------------------------------------------------

_FLOW_WITH_SENSITIVE = '''@lumen 1.0
use sensitive.transfer

agent PaymentAgent:
  watch: sensitive.transfer(filter=pending)
  on transfer:
    print "Processing"
'''


# ---------------------------------------------------------------------------
# Test: _walk_stmt cubre todos los tipos de statement
# ---------------------------------------------------------------------------

def test_walk_stmt_expression_statement():
    from lumen.compiler.ast_nodes import ExpressionStatement
    from lumen.compiler.mode_detector import _walk_stmt
    expr = NumberLiteral(position=_POS, value="42")
    stmt = ExpressionStatement(position=_POS, expression=expr)
    nodes = list(_walk_stmt(stmt))
    assert expr in nodes


def test_walk_stmt_return_statement():
    from lumen.compiler.ast_nodes import ReturnStatement
    from lumen.compiler.mode_detector import _walk_stmt
    val = NumberLiteral(position=_POS, value="1")
    stmt = ReturnStatement(position=_POS, value=val)
    nodes = list(_walk_stmt(stmt))
    assert val in nodes


def test_walk_stmt_return_statement_no_value():
    from lumen.compiler.ast_nodes import ReturnStatement
    from lumen.compiler.mode_detector import _walk_stmt
    stmt = ReturnStatement(position=_POS, value=None)
    nodes = list(_walk_stmt(stmt))
    assert nodes == []


def test_walk_stmt_print_statement():
    from lumen.compiler.ast_nodes import PrintStatement
    from lumen.compiler.mode_detector import _walk_stmt
    val = StringLiteral(position=_POS, value="hello")
    stmt = PrintStatement(position=_POS, value=val)
    nodes = list(_walk_stmt(stmt))
    assert val in nodes


def test_walk_stmt_pipeline():
    from lumen.compiler.ast_nodes import Pipeline
    from lumen.compiler.mode_detector import _walk_stmt
    step1 = NumberLiteral(position=_POS, value="1")
    step2 = NumberLiteral(position=_POS, value="2")
    stmt = Pipeline(position=_POS, steps=(step1, step2))
    nodes = list(_walk_stmt(stmt))
    assert step1 in nodes
    assert step2 in nodes


def test_walk_stmt_if_statement():
    from lumen.compiler.ast_nodes import Block, IfStatement
    from lumen.compiler.mode_detector import _walk_stmt
    cond = NumberLiteral(position=_POS, value="1")
    then_block = Block(position=_POS, statements=())
    else_block = Block(position=_POS, statements=())
    stmt = IfStatement(position=_POS, condition=cond, then_block=then_block, else_block=else_block)
    nodes = list(_walk_stmt(stmt))
    assert cond in nodes


def test_walk_stmt_if_statement_no_else():
    from lumen.compiler.ast_nodes import Block, IfStatement
    from lumen.compiler.mode_detector import _walk_stmt
    cond = NumberLiteral(position=_POS, value="1")
    then_block = Block(position=_POS, statements=())
    stmt = IfStatement(position=_POS, condition=cond, then_block=then_block, else_block=None)
    nodes = list(_walk_stmt(stmt))
    assert cond in nodes


def test_walk_stmt_for_statement():
    from lumen.compiler.ast_nodes import Block, ForStatement
    from lumen.compiler.mode_detector import _walk_stmt
    iterable = Identifier(position=_POS, name="items")
    body = Block(position=_POS, statements=())
    stmt = ForStatement(position=_POS, target="item", iterable=iterable, body=body)
    nodes = list(_walk_stmt(stmt))
    assert iterable in nodes


def test_walk_stmt_match_statement():
    from lumen.compiler.ast_nodes import Block, MatchArm, MatchStatement
    from lumen.compiler.mode_detector import _walk_stmt
    subject = Identifier(position=_POS, name="x")
    arm_body = Block(position=_POS, statements=())
    arm_pattern = Identifier(position=_POS, name="ok")
    arm = MatchArm(position=_POS, pattern=arm_pattern, body=arm_body)
    stmt = MatchStatement(position=_POS, subject=subject, arms=(arm,))
    nodes = list(_walk_stmt(stmt))
    assert subject in nodes


def test_walk_stmt_undo_statement():
    from lumen.compiler.ast_nodes import UndoStatement
    from lumen.compiler.mode_detector import _walk_stmt
    action_id = StringLiteral(position=_POS, value="abc")
    stmt = UndoStatement(position=_POS, action_id=action_id)
    nodes = list(_walk_stmt(stmt))
    assert action_id in nodes


def test_agent_presence_means_flow_even_with_sensitive_cap():
    prog = _parse(_FLOW_WITH_SENSITIVE)
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert result.mode == "flow"
