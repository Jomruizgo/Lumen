"""Tests de los nodos AST de Lumen."""

from __future__ import annotations

import pytest

from lumen.compiler.ast_nodes import (
    ActionBody,
    ActionDecl,
    AgentBody,
    AgentDecl,
    Assignment,
    AuditClause,
    AuditLogCall,
    BecauseAnnotation,
    BinaryOp,
    Block,
    BooleanLiteral,
    CapabilityCall,
    CapabilityDecl,
    ConfigClause,
    DotAccess,
    ExecuteClause,
    ExpressionStatement,
    ForStatement,
    FunctionCall,
    FunctionDecl,
    Identifier,
    IfStatement,
    ImportDecl,
    MatchArm,
    MatchStatement,
    MoneyLiteral,
    NumberLiteral,
    OnClause,
    Param,
    PassStatement,
    Pipeline,
    PrimitiveType,
    PrintStatement,
    Program,
    RequiresClause,
    ResolveBlock,
    ReturnStatement,
    ReversibleClause,
    ScheduleClause,
    SourcePosition,
    StateClause,
    StrategyClause,
    StringInterpolation,
    StringLiteral,
    TimeLiteral,
    UnionType,
    VersionDecl,
    WatchClause,
)


def make_pos(line: int = 1, col: int = 1) -> SourcePosition:
    return SourcePosition(line=line, col=col)


# ---------------------------------------------------------------------------
# SourcePosition
# ---------------------------------------------------------------------------


def test_source_position_frozen() -> None:
    """SourcePosition es inmutable."""
    pos = make_pos(1, 1)
    with pytest.raises(Exception):
        pos.line = 2  # type: ignore[misc]


def test_source_position_str() -> None:
    pos = SourcePosition(line=5, col=10, file="test.lumen")
    assert "5" in str(pos)
    assert "10" in str(pos)
    assert "test.lumen" in str(pos)


def test_source_position_no_file() -> None:
    pos = make_pos(3, 7)
    assert str(pos) == "3:7"


# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------


def test_number_literal() -> None:
    pos = make_pos()
    node = NumberLiteral(position=pos, value="42")
    assert node.value == "42"
    assert "42" in node.pretty_print()


def test_string_literal() -> None:
    pos = make_pos()
    node = StringLiteral(position=pos, value="hello")
    assert '"hello"' in node.pretty_print()


def test_boolean_literal_true() -> None:
    pos = make_pos()
    node = BooleanLiteral(position=pos, value=True)
    assert "true" in node.pretty_print()


def test_boolean_literal_false() -> None:
    pos = make_pos()
    node = BooleanLiteral(position=pos, value=False)
    assert "false" in node.pretty_print()


def test_time_literal() -> None:
    pos = make_pos()
    node = TimeLiteral(position=pos, value="5min")
    assert "5min" in node.pretty_print()


def test_money_literal() -> None:
    pos = make_pos()
    node = MoneyLiteral(position=pos, value="$100 USD", amount="100", currency="USD")
    assert "$100 USD" in node.pretty_print()
    assert node.currency == "USD"


# ---------------------------------------------------------------------------
# Identifier & Expressions
# ---------------------------------------------------------------------------


def test_identifier() -> None:
    pos = make_pos()
    node = Identifier(position=pos, name="my_var")
    assert "my_var" in node.pretty_print()


def test_binary_op() -> None:
    pos = make_pos()
    left = NumberLiteral(position=pos, value="2")
    right = NumberLiteral(position=pos, value="3")
    node = BinaryOp(position=pos, op="+", left=left, right=right)
    pp = node.pretty_print()
    assert "2" in pp
    assert "3" in pp
    assert "+" in pp


def test_function_call() -> None:
    pos = make_pos()
    arg = NumberLiteral(position=pos, value="1")
    node = FunctionCall(position=pos, name="add", args=(arg,), kwargs=())
    pp = node.pretty_print()
    assert "add" in pp
    assert "1" in pp


def test_function_call_with_kwargs() -> None:
    pos = make_pos()
    val = StringLiteral(position=pos, value="test")
    node = FunctionCall(position=pos, name="send", args=(), kwargs=(("to", val),))
    pp = node.pretty_print()
    assert "to=" in pp


def test_capability_call() -> None:
    pos = make_pos()
    node = CapabilityCall(position=pos, path=("comm", "email"), args=(), kwargs=())
    pp = node.pretty_print()
    assert "comm.email" in pp


def test_dot_access() -> None:
    pos = make_pos()
    obj = Identifier(position=pos, name="obj")
    node = DotAccess(position=pos, obj=obj, field="field")
    pp = node.pretty_print()
    assert "obj.field" in pp


def test_string_interpolation() -> None:
    pos = make_pos()
    var = Identifier(position=pos, name="name")
    node = StringInterpolation(position=pos, parts=("Hello, ", var, "!"))
    pp = node.pretty_print()
    assert "Hello" in pp
    assert "name" in pp


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


def test_primitive_type() -> None:
    pos = make_pos()
    node = PrimitiveType(position=pos, name="number")
    assert "number" in node.pretty_print()


def test_union_type() -> None:
    pos = make_pos()
    left = PrimitiveType(position=pos, name="text")
    right = PrimitiveType(position=pos, name="number")
    node = UnionType(position=pos, left=left, right=right)
    pp = node.pretty_print()
    assert "text" in pp
    assert "number" in pp
    assert "|" in pp


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


def test_assignment() -> None:
    pos = make_pos()
    val = NumberLiteral(position=pos, value="42")
    node = Assignment(position=pos, target="x", value=val)
    pp = node.pretty_print()
    assert "x = 42" in pp


def test_assignment_with_because() -> None:
    pos = make_pos()
    val = NumberLiteral(position=pos, value="0.16")
    because = BecauseAnnotation(position=pos, reason="IVA Mexico")
    node = Assignment(position=pos, target="tax", value=val, because=because)
    pp = node.pretty_print()
    assert "IVA Mexico" in pp


def test_return_statement_with_value() -> None:
    pos = make_pos()
    val = NumberLiteral(position=pos, value="1")
    node = ReturnStatement(position=pos, value=val)
    pp = node.pretty_print()
    assert "return" in pp
    assert "1" in pp


def test_return_statement_no_value() -> None:
    pos = make_pos()
    node = ReturnStatement(position=pos)
    assert "return" in node.pretty_print()


def test_pass_statement() -> None:
    pos = make_pos()
    node = PassStatement(position=pos)
    assert "pass" in node.pretty_print()


def test_if_statement() -> None:
    pos = make_pos()
    cond = BooleanLiteral(position=pos, value=True)
    ret = ReturnStatement(position=pos, value=NumberLiteral(position=pos, value="1"))
    block = Block(position=pos, statements=(ret,))
    node = IfStatement(position=pos, condition=cond, then_block=block)
    pp = node.pretty_print()
    assert "if" in pp
    assert "return" in pp


def test_for_statement() -> None:
    pos = make_pos()
    iterable = Identifier(position=pos, name="items")
    body = Block(position=pos, statements=(PassStatement(position=pos),))
    node = ForStatement(position=pos, target="item", iterable=iterable, body=body)
    pp = node.pretty_print()
    assert "for" in pp
    assert "item" in pp
    assert "items" in pp


def test_pipeline() -> None:
    pos = make_pos()
    step1 = Identifier(position=pos, name="data")
    step2 = Identifier(position=pos, name="transform")
    node = Pipeline(position=pos, steps=(step1, step2))
    pp = node.pretty_print()
    assert "data" in pp
    assert "|" in pp
    assert "transform" in pp


def test_resolve_block() -> None:
    pos = make_pos()
    subject = StringLiteral(position=pos, value="ambiguous")
    action = ExpressionStatement(position=pos, expression=Identifier(position=pos, name="fail_safe"))
    block = Block(position=pos, statements=(action,))
    strategy = StrategyClause(position=pos, name="unknown", body=block)
    node = ResolveBlock(position=pos, subject=subject, strategies=(strategy,))
    pp = node.pretty_print()
    assert "resolve" in pp
    assert "unknown" in pp


# ---------------------------------------------------------------------------
# Clauses
# ---------------------------------------------------------------------------


def test_requires_clause() -> None:
    pos = make_pos()
    cond = BinaryOp(
        position=pos,
        op=">",
        left=Identifier(position=pos, name="amount"),
        right=NumberLiteral(position=pos, value="0"),
    )
    node = RequiresClause(position=pos, condition=cond)
    pp = node.pretty_print()
    assert "requires" in pp
    assert "amount" in pp


def test_reversible_clause_true() -> None:
    pos = make_pos()
    node = ReversibleClause(position=pos, value=True)
    pp = node.pretty_print()
    assert "reversible: true" in pp


def test_reversible_clause_false() -> None:
    pos = make_pos()
    node = ReversibleClause(position=pos, value=False)
    pp = node.pretty_print()
    assert "reversible: false" in pp


def test_reversible_clause_duration() -> None:
    pos = make_pos()
    node = ReversibleClause(position=pos, value="24h")
    pp = node.pretty_print()
    assert "24h" in pp


def test_audit_clause() -> None:
    pos = make_pos()
    node = AuditClause(position=pos, level="full")
    pp = node.pretty_print()
    assert "audit: full" in pp


def test_watch_clause() -> None:
    pos = make_pos()
    expr = Identifier(position=pos, name="comm")
    node = WatchClause(position=pos, expression=expr)
    pp = node.pretty_print()
    assert "watch:" in pp


def test_schedule_clause() -> None:
    pos = make_pos()
    expr = StringLiteral(position=pos, value="0 8 * * *")
    node = ScheduleClause(position=pos, expression=expr)
    pp = node.pretty_print()
    assert "schedule:" in pp


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------


def test_version_decl() -> None:
    pos = make_pos()
    node = VersionDecl(position=pos, major=1, minor=0)
    pp = node.pretty_print()
    assert "@lumen 1.0" in pp


def test_capability_decl() -> None:
    pos = make_pos()
    node = CapabilityDecl(position=pos, path=("comm", "email"))
    pp = node.pretty_print()
    assert "use comm.email" in pp


def test_capability_decl_with_alias() -> None:
    pos = make_pos()
    node = CapabilityDecl(position=pos, path=("data", "search"), alias="search")
    pp = node.pretty_print()
    assert "as search" in pp


def test_import_decl_std() -> None:
    pos = make_pos()
    node = ImportDecl(position=pos, path="math", from_std=True)
    pp = node.pretty_print()
    assert "from std" in pp


def test_function_decl() -> None:
    pos = make_pos()
    param = Param(position=pos, name="x")
    ret = ReturnStatement(position=pos, value=Identifier(position=pos, name="x"))
    body = Block(position=pos, statements=(ret,))
    node = FunctionDecl(position=pos, name="identity", params=(param,), body=body)
    pp = node.pretty_print()
    assert "fn identity" in pp
    assert "return" in pp


def test_action_decl() -> None:
    pos = make_pos()
    rev = ReversibleClause(position=pos, value="24h")
    audit = AuditClause(position=pos, level="full")
    ret = ReturnStatement(position=pos)
    exec_body = Block(position=pos, statements=(ret,))
    exec_clause = ExecuteClause(position=pos, body=exec_body)
    body = ActionBody(
        position=pos,
        reversible=rev,
        audit=audit,
        execute=exec_clause,
    )
    node = ActionDecl(position=pos, name="do_thing", params=(), body=body)
    pp = node.pretty_print()
    assert "action do_thing" in pp
    assert "reversible" in pp


def test_agent_decl() -> None:
    pos = make_pos()
    expr = Identifier(position=pos, name="comm")
    watch = WatchClause(position=pos, expression=expr)
    on_pattern = Identifier(position=pos, name="tick")
    on_body = Block(position=pos, statements=(PassStatement(position=pos),))
    on_clause = OnClause(position=pos, pattern=on_pattern, body=on_body)
    agent_body = AgentBody(
        position=pos,
        watch=watch,
        on_clauses=(on_clause,),
    )
    node = AgentDecl(position=pos, name="monitor", body=agent_body)
    pp = node.pretty_print()
    assert "agent monitor" in pp


# ---------------------------------------------------------------------------
# Program
# ---------------------------------------------------------------------------


def test_program() -> None:
    pos = make_pos()
    version = VersionDecl(position=pos, major=1, minor=0)
    program = Program(position=pos, version=version, top_levels=())
    pp = program.pretty_print()
    assert "@lumen 1.0" in pp


def test_program_with_capabilities() -> None:
    pos = make_pos()
    version = VersionDecl(position=pos, major=1, minor=0)
    cap = CapabilityDecl(position=pos, path=("comm", "email"))
    program = Program(position=pos, version=version, top_levels=(cap,))
    assert len(program.capabilities) == 1
    assert program.capabilities[0].path_str == "comm.email"


def test_program_immutable() -> None:
    pos = make_pos()
    version = VersionDecl(position=pos, major=1, minor=0)
    program = Program(position=pos, version=version, top_levels=())
    with pytest.raises(Exception):
        program.version = version  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AuditLogCall
# ---------------------------------------------------------------------------


def test_audit_log_call() -> None:
    pos = make_pos()
    node = AuditLogCall(position=pos, action_name="pay", level="full", event_type="execution")
    pp = node.pretty_print()
    assert "__audit_log__" in pp
    assert "pay" in pp


# ---------------------------------------------------------------------------
# Param
# ---------------------------------------------------------------------------


def test_param_with_type_and_default() -> None:
    pos = make_pos()
    typ = PrimitiveType(position=pos, name="number")
    default = NumberLiteral(position=pos, value="0")
    node = Param(position=pos, name="x", type_annotation=typ, default=default)
    pp = node.pretty_print()
    assert "x" in pp
    assert "number" in pp
    assert "0" in pp
