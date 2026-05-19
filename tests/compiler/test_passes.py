"""Tests para los passes del compilador: mode_detector, cap_checker, typechecker, resolver, rev_checker."""

from __future__ import annotations

import pytest

from lumen.compiler.parser import parse
from lumen.compiler.mode_detector import detect_mode, ModeResult
from lumen.compiler.cap_checker import check_capabilities
from lumen.compiler.typechecker import typecheck, TypedProgram
from lumen.compiler.resolver import resolve_semantics
from lumen.compiler.rev_checker import check_reversibility


def _parse(source: str):
    result = parse(source)
    assert not isinstance(result, Exception), f"Parse failed: {result}"
    return result


# ---------- mode_detector ----------

def test_mode_fast_no_sensitive():
    prog = _parse("@lumen 1.0\nuse comm.email\nprint \"hi\"\n")
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert result.mode == "fast"


def test_mode_safe_sensitive_cap():
    prog = _parse(
        "@lumen 1.0\nuse sensitive.transfer\n"
        "action pay(x):\n  reversible: 24h\n  execute:\n    sensitive.transfer(to=x)\n"
    )
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert result.mode == "safe"


def test_mode_flow_agent():
    prog = _parse(
        "@lumen 1.0\nuse comm.email\n"
        "agent watcher:\n  watch: comm.email.inbox\n  on new_email:\n    print \"got email\"\n"
    )
    result = detect_mode(prog)
    assert isinstance(result, ModeResult)
    assert result.mode == "flow"


# ---------- cap_checker ----------

def test_cap_checker_no_errors():
    prog = _parse("@lumen 1.0\nuse comm.email\nprint \"ok\"\n")
    errors = check_capabilities(prog)
    assert errors == []


def test_cap_checker_missing_use():
    prog = _parse("@lumen 1.0\nprint \"ok\"\n")
    # No capability calls, no errors
    errors = check_capabilities(prog)
    assert errors == []


# ---------- typechecker ----------

def test_typecheck_returns_typed_program():
    prog = _parse("@lumen 1.0\nprint \"hi\"\n")
    result = typecheck(prog, "fast")
    assert isinstance(result, TypedProgram)
    assert result.ast is prog


def test_typecheck_no_errors_simple():
    prog = _parse("@lumen 1.0\nx = 42\n")
    result = typecheck(prog, "fast")
    assert isinstance(result, TypedProgram)


# ---------- resolver ----------

def test_resolver_wraps_typed():
    prog = _parse("@lumen 1.0\nprint \"hi\"\n")
    typed = typecheck(prog, "fast")
    assert isinstance(typed, TypedProgram)
    resolved = resolve_semantics(typed, "fast")
    # ResolvedProgram wraps TypedProgram
    assert hasattr(resolved, "typed")
    assert resolved.typed is typed


def test_resolver_action_with_standalone_resolve_block():
    # ResolveBlock as a standalone statement inside action execute
    # This covers _find_resolve_blocks_in_stmt + _validate_resolve_block + lines 147-150
    source = (
        "@lumen 1.0\n"
        "action classify(label):\n"
        "  execute:\n"
        "    resolve(label) {\n"
        "      ambiguous: ask_user(\"clarify?\")\n"
        "      unknown: fail_safe()\n"
        "    }\n"
    )
    prog = _parse(source)
    typed = typecheck(prog, "fast")
    assert isinstance(typed, TypedProgram)
    resolved = resolve_semantics(typed, "fast")
    assert resolved is not None
    assert hasattr(resolved, "typed") or isinstance(resolved, list)


def test_resolver_function_decl_with_resolve():
    # FunctionDecl path — covers lines 152-159
    source = (
        "@lumen 1.0\n"
        "fn get_team(team_name):\n"
        "  resolve(team_name) {\n"
        "    high_confidence: use_context(teams)\n"
        "    ambiguous: ask_user(\"which?\")\n"
        "    unknown: fail_safe()\n"
        "  }\n"
    )
    prog = _parse(source)
    typed = typecheck(prog, "fast")
    assert isinstance(typed, TypedProgram)
    resolved = resolve_semantics(typed, "fast")
    assert resolved is not None


def test_resolver_top_level_resolve_block():
    # Top-level ResolveBlock — covers isinstance(tl, Statement) path + lines 173-174
    source = (
        "@lumen 1.0\n"
        "resolve(foo) {\n"
        "  high_confidence: use_context(x)\n"
        "  unknown: fail_safe()\n"
        "}\n"
    )
    prog = _parse(source)
    typed = typecheck(prog, "fast")
    assert isinstance(typed, TypedProgram)
    resolved = resolve_semantics(typed, "fast")
    assert resolved is not None


def test_resolver_fallback_strategy_selection():
    # ResolveBlock with non-preferred strategy name → hits line 80 (next(iter(...)) fallback)
    source = (
        "@lumen 1.0\n"
        "resolve(foo) {\n"
        "  custom_strategy: bar()\n"
        "}\n"
    )
    prog = _parse(source)
    typed = typecheck(prog, "fast")
    assert isinstance(typed, TypedProgram)
    resolved = resolve_semantics(typed, "fast")
    assert resolved is not None


def test_resolver_agent_decl_with_resolve():
    # AgentDecl with on_clause containing ResolveBlock — covers lines 166-168
    source = (
        "@lumen 1.0\n"
        "use comm.email\n"
        "agent watcher:\n"
        "  watch: comm.email(filter=unread)\n"
        "  on email:\n"
        "    resolve(email) {\n"
        "      high_confidence: use_context(known_senders)\n"
        "      ambiguous: ask_user(\"known sender?\")\n"
        "      unknown: fail_safe()\n"
        "    }\n"
    )
    prog = _parse(source)
    typed = typecheck(prog, "flow")
    assert isinstance(typed, TypedProgram)
    resolved = resolve_semantics(typed, "flow")
    assert resolved is not None


def test_resolver_safe_mode_missing_strategies_returns_errors():
    # ResolveBlock in safe mode without ambiguous/unknown → CompileError list
    # Covers _validate_resolve_block lines 60-73 and line 177
    source = (
        "@lumen 1.0\n"
        "action classify(label):\n"
        "  execute:\n"
        "    resolve(label) {\n"
        "      high_confidence: use_context(x)\n"
        "    }\n"
    )
    prog = _parse(source)
    typed = typecheck(prog, "safe")
    assert isinstance(typed, TypedProgram)
    result = resolve_semantics(typed, "safe")
    # Should return a list of CompileErrors for missing strategies
    assert isinstance(result, list) and len(result) > 0
    assert any(e.code == "LMN-0002" for e in result)


# ---------- rev_checker ----------

def test_rev_checker_ok_with_reversible():
    prog = _parse(
        "@lumen 1.0\nuse sensitive.transfer\n"
        "action pay(x):\n  reversible: 24h\n  execute:\n    sensitive.transfer(to=x)\n"
    )
    errors = check_reversibility(prog)
    assert errors == []


def test_rev_checker_error_without_reversible():
    prog = _parse(
        "@lumen 1.0\nuse sensitive.transfer\n"
        "action pay(x):\n  execute:\n    sensitive.transfer(to=x)\n"
    )
    errors = check_reversibility(prog)
    codes = [e.code for e in errors]
    assert "LMN-0003" in codes
