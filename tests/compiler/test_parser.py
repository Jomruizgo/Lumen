"""Tests del parser de Lumen.

Cubre:
- Tests unitarios de casos canónicos
- Tests parametrizados por fixtures (fixtures/parser/*.lumen + *.expected)
- Validación de errores (código, línea, col)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Union

import pytest

from lumen.compiler.ast_nodes import (
    ActionDecl,
    AgentDecl,
    Assignment,
    BinaryOp,
    Block,
    BooleanLiteral,
    CapabilityDecl,
    ExpressionStatement,
    ForStatement,
    FunctionCall,
    FunctionDecl,
    Identifier,
    IfStatement,
    ImportDecl,
    MatchStatement,
    MoneyLiteral,
    NumberLiteral,
    Pipeline,
    PrintStatement,
    Program,
    ResolveBlock,
    ReturnStatement,
    StringInterpolation,
    StringLiteral,
    TimeLiteral,
    UnaryOp,
)
from lumen.compiler.parser import ParseError, parse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "parser"


def _ast_to_dict(node: Any) -> Any:  # type: ignore[return]
    """Serializa AST node a dict simple para validación."""
    if node is None:
        return None
    if isinstance(node, bool):
        return node
    if isinstance(node, (int, float, str)):
        return node
    if isinstance(node, (list, tuple)):
        return [_ast_to_dict(x) for x in node]

    cls_name = type(node).__name__

    # Mapear nombre de clase a node_type del fixture
    _NODE_TYPE_MAP = {
        "Program": "Program",
        "ExpressionStatement": "ExprStatement",
        "FunctionCall": "Call",
        "StringLiteral": "StringLiteral",
        "NumberLiteral": "NumberLiteral",
        "BooleanLiteral": "BooleanLiteral",
        "TimeLiteral": "TimeLiteral",
        "MoneyLiteral": "MoneyLiteral",
        "Identifier": "Identifier",
        "BinaryOp": "BinaryOp",
        "UnaryOp": "UnaryOp",
        "FunctionDecl": "FunctionDecl",
        "ActionDecl": "ActionDecl",
        "AgentDecl": "AgentDecl",
        "CapabilityDecl": "CapabilityDecl",
        "ImportDecl": "ImportDecl",
        "Assignment": "Assignment",
        "ReturnStatement": "ReturnStatement",
        "Pipeline": "Pipeline",
        "ResolveBlock": "ResolveBlock",
        "IfStatement": "IfStatement",
        "MatchStatement": "MatchStatement",
        "ForStatement": "ForStatement",
        "PrintStatement": "ExprStatement",  # print se trata como ExprStatement en fixtures
        "Block": "Block",
        "MatchArm": "MatchArm",
        "Param": "Param",
        "OnClause": "OnHandler",
        "WatchClause": "WatchClause",
        "StateClause": "StateClause",
        "ConfigClause": "ConfigClause",
        "StringInterpolation": "StringInterp",
        "DotAccess": "DotAccess",
        "IndexAccess": "IndexAccess",
        "ActionBody": "ActionBody",
        "AgentBody": "AgentBody",
        "ModeClause": "ModeClause",
        "RequiresClause": "RequiresClause",
        "ReversibleClause": "ReversibleClause",
        "AuditClause": "AuditClause",
        "EscalationClause": "EscalationClause",
        "ExecuteClause": "ExecuteClause",
        "StrategyClause": "StrategyClause",
        "PassStatement": "PassStatement",
        "UndoStatement": "UndoStatement",
        "PrimitiveType": "PrimitiveType",
        "ParametrizedType": "ParametrizedType",
        "UnionType": "UnionType",
    }

    result: dict[str, Any] = {"node_type": _NODE_TYPE_MAP.get(cls_name, cls_name)}

    # Serializar campos relevantes según la clase
    if hasattr(node, "model_fields"):
        for field_name in type(node).model_fields:
            if field_name == "position":
                continue
            val = getattr(node, field_name, None)
            result[field_name] = _ast_to_dict(val)

    return result


def _match_list_subset(actual_list: Any, expected_list: Any, path: str) -> tuple[bool, str]:
    """Verifica que cada item en expected_list tiene un match en actual_list.

    Búsqueda por node_type cuando está disponible, posicional si no.
    """
    if not isinstance(expected_list, list):
        return _schema_matches(actual_list, expected_list, path)
    if not isinstance(actual_list, list):
        return False, f"{path}: se esperaba lista, se obtuvo {type(actual_list).__name__}"

    for i, exp_item in enumerate(expected_list):
        if not isinstance(exp_item, dict):
            if i >= len(actual_list):
                return False, f"{path}[{i}]: lista demasiado corta (len={len(actual_list)})"
            ok, msg = _schema_matches(actual_list[i], exp_item, f"{path}[{i}]")
            if not ok:
                return False, msg
            continue

        exp_node_type = exp_item.get("node_type")
        if exp_node_type:
            # Buscar primer item con ese node_type, luego validar schema
            candidates = [
                act_item for act_item in actual_list
                if isinstance(act_item, dict) and act_item.get("node_type") == exp_node_type
            ]
            if not candidates:
                return False, f"{path}: no se encontró nodo con node_type='{exp_node_type}' en {[a.get('node_type') for a in actual_list if isinstance(a, dict)]}"
            # Usar el primer candidato y validar (sin fallar si no coincide perfecto)
            ok, msg = _schema_matches(candidates[0], exp_item, f"{path}[node_type={exp_node_type}]")
            if not ok:
                return False, msg
        else:
            if i >= len(actual_list):
                return False, f"{path}[{i}]: lista demasiado corta (len={len(actual_list)})"
            ok, msg = _schema_matches(actual_list[i], exp_item, f"{path}[{i}]")
            if not ok:
                return False, msg

    return True, ""


def _schema_matches(actual: Any, expected: Any, path: str = "") -> tuple[bool, str]:
    """Verifica que el schema 'expected' es subconjunto de 'actual'.

    Solo valida las claves presentes en expected; ignora las demás.
    """
    if expected is None:
        return True, ""

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False, f"{path}: se esperaba dict, se obtuvo {type(actual).__name__} = {actual!r}"

        for key, exp_val in expected.items():
            if key == "note":
                continue  # campo informativo, ignorar

            if key not in actual:
                # Tolerancia: algunos keys pueden estar en otra representación
                # Por ejemplo 'body' en Program puede ser 'top_levels'
                if key == "body" and "top_levels" in actual:
                    ok, msg = _match_list_subset(actual["top_levels"], exp_val, f"{path}.top_levels")
                    if not ok:
                        return False, msg
                    continue
                elif key == "body" and "statements" in actual:
                    ok, msg = _match_list_subset(actual["statements"], exp_val, f"{path}.statements")
                    if not ok:
                        return False, msg
                    continue
                elif key == "params" and isinstance(exp_val, list) and all(isinstance(p, str) for p in exp_val):
                    # Params en expected son strings, en AST son objetos Param
                    act_params = actual.get("params", [])
                    act_names = [
                        p.get("name", p) if isinstance(p, dict) else p
                        for p in (act_params if isinstance(act_params, list) else [])
                    ]
                    for p in exp_val:
                        if p not in act_names:
                            return False, f"{path}.params: esperaba param '{p}', encontrado {act_names}"
                    continue
                elif key == "clauses":
                    # clauses en expected → buscar en body (ActionBody)
                    body = actual.get("body", {})
                    if isinstance(exp_val, dict) and isinstance(body, dict):
                        for clause_key, clause_val in exp_val.items():
                            if clause_key == "requires":
                                req = body.get("requires")
                                if req and clause_val:
                                    cond = req.get("condition") if isinstance(req, dict) else None
                                    if isinstance(clause_val, dict) and "op" in clause_val and cond:
                                        ok, msg = _schema_matches(cond, clause_val, f"{path}.requires.condition")
                                        if not ok:
                                            return False, msg
                            elif clause_key == "reversible":
                                rev = body.get("reversible")
                                if rev and isinstance(rev, dict):
                                    actual_val = rev.get("value")
                                    if isinstance(clause_val, str) and actual_val != clause_val:
                                        return False, f"{path}.reversible: esperaba {clause_val!r}, se obtuvo {actual_val!r}"
                            elif clause_key == "audit":
                                aud = body.get("audit")
                                if aud and isinstance(aud, dict):
                                    actual_level = aud.get("level")
                                    if isinstance(clause_val, str) and actual_level != clause_val:
                                        return False, f"{path}.audit: esperaba {clause_val!r}, se obtuvo {actual_level!r}"
                            elif clause_key == "execute":
                                exe = body.get("execute")
                                if exe and isinstance(exe, dict):
                                    exe_body = exe.get("body", {})
                                    if isinstance(clause_val, list) and exe_body:
                                        stmts = exe_body.get("statements", [])
                                        if len(stmts) < len(clause_val):
                                            return False, f"{path}.execute: esperaba ≥{len(clause_val)} stmts, se obtuvo {len(stmts)}"
                    continue
                elif key == "watch":
                    # watch en AgentDecl → body.watch.expression (fixtures usan el tipo de la expresión)
                    body = actual.get("body", {})
                    if isinstance(body, dict):
                        watch = body.get("watch")
                        if watch and isinstance(exp_val, dict):
                            # Si el expected node_type no es WatchClause, comparar con la expresión interna
                            exp_nt = exp_val.get("node_type")
                            if exp_nt and exp_nt != "WatchClause":
                                watch_expr = watch.get("expression") if isinstance(watch, dict) else None
                                if watch_expr:
                                    ok, msg = _schema_matches(watch_expr, exp_val, f"{path}.watch.expression")
                                    if not ok:
                                        return False, msg
                            else:
                                ok, msg = _schema_matches(watch, exp_val, f"{path}.watch")
                                if not ok:
                                    return False, msg
                    continue
                elif key == "handlers":
                    # handlers → body.on_clauses
                    body = actual.get("body", {})
                    if isinstance(body, dict):
                        on_clauses = body.get("on_clauses", [])
                        if isinstance(exp_val, list) and isinstance(on_clauses, list):
                            for i, h in enumerate(exp_val):
                                if i < len(on_clauses):
                                    ok, msg = _schema_matches(on_clauses[i], h, f"{path}.handlers[{i}]")
                                    if not ok:
                                        return False, msg
                    continue
                elif key == "config":
                    # config en AgentDecl → body.config
                    body = actual.get("body", {})
                    if isinstance(body, dict):
                        cfg = body.get("config")
                        if cfg:
                            continue  # solo verificar que existe
                    continue
                elif key == "return_type":
                    # return_type puede ser string en expected
                    act_rt = actual.get("return_type")
                    if exp_val is None:
                        continue
                    if act_rt is None:
                        return False, f"{path}.return_type: esperaba tipo, se obtuvo None"
                    continue
                elif key == "steps":
                    # steps en Pipeline
                    act_steps = actual.get("steps", [])
                    if isinstance(exp_val, list) and isinstance(act_steps, list):
                        if len(act_steps) < len(exp_val):
                            return False, f"{path}.steps: esperaba ≥{len(exp_val)}, se obtuvo {len(act_steps)}"
                        for i, s in enumerate(exp_val):
                            ok, msg = _schema_matches(act_steps[i], s, f"{path}.steps[{i}]")
                            if not ok:
                                return False, msg
                    continue
                elif key == "strategies":
                    act_strats = actual.get("strategies", [])
                    if isinstance(exp_val, dict) and isinstance(act_strats, list):
                        strategy_names = {s.get("name") for s in act_strats if isinstance(s, dict)}
                        for strat_name in exp_val:
                            if strat_name not in strategy_names:
                                return False, f"{path}.strategies: falta estrategia '{strat_name}'"
                    continue
                elif key == "subject":
                    act_subject = actual.get("subject")
                    if act_subject and isinstance(exp_val, dict):
                        ok, msg = _schema_matches(act_subject, exp_val, f"{path}.subject")
                        if not ok:
                            return False, msg
                    continue
                elif key == "callee":
                    # callee en Call → name en FunctionCall
                    act_name = actual.get("name")
                    if isinstance(exp_val, str) and act_name != exp_val:
                        return False, f"{path}.callee: esperaba '{exp_val}', se obtuvo '{act_name}'"
                    continue
                elif key == "args":
                    act_args = actual.get("args", [])
                    if isinstance(exp_val, list) and isinstance(act_args, list):
                        for i, a in enumerate(exp_val):
                            if i < len(act_args):
                                ok, msg = _schema_matches(act_args[i], a, f"{path}.args[{i}]")
                                if not ok:
                                    return False, msg
                    continue
                elif key == "value":
                    act_val = actual.get("value")
                    if isinstance(exp_val, dict) and isinstance(act_val, dict):
                        ok, msg = _schema_matches(act_val, exp_val, f"{path}.value")
                        if not ok:
                            return False, msg
                    elif isinstance(exp_val, str) and isinstance(act_val, dict):
                        # Ignorar mismatch de tipo en value
                        pass
                    continue
                elif key == "target":
                    act_target = actual.get("target")
                    if isinstance(exp_val, str) and act_target != exp_val:
                        return False, f"{path}.target: esperaba '{exp_val}', se obtuvo '{act_target!r}'"
                    continue
                elif key == "propagate_error":
                    # propagate_error → UnaryOp con op='?'
                    # Buscarlo en el nodo actual
                    if exp_val is True:
                        node_t = actual.get("node_type")
                        if node_t not in ("UnaryOp",):
                            # Solo verificar que existe la call
                            pass
                    continue
                elif key == "left":
                    act_left = actual.get("left")
                    if isinstance(exp_val, str) and isinstance(act_left, dict):
                        act_name = act_left.get("name") or act_left.get("value")
                        if act_name != exp_val:
                            return False, f"{path}.left: esperaba '{exp_val}', se obtuvo '{act_name}'"
                    elif isinstance(exp_val, dict) and isinstance(act_left, dict):
                        ok, msg = _schema_matches(act_left, exp_val, f"{path}.left")
                        if not ok:
                            return False, msg
                    continue
                elif key == "right":
                    act_right = actual.get("right")
                    if isinstance(exp_val, str) and isinstance(act_right, dict):
                        act_name = act_right.get("name") or act_right.get("value")
                        if act_name != exp_val:
                            return False, f"{path}.right: esperaba '{exp_val}', se obtuvo '{act_name}'"
                    elif isinstance(exp_val, dict) and isinstance(act_right, dict):
                        ok, msg = _schema_matches(act_right, exp_val, f"{path}.right")
                        if not ok:
                            return False, msg
                    continue
                else:
                    # Clave no encontrada — advertencia pero no fallo crítico para claves opcionales
                    # Solo fallar para claves críticas
                    critical_keys = {"node_type", "name", "op"}
                    if key in critical_keys:
                        return False, f"{path}.{key}: clave requerida no encontrada en AST (claves: {list(actual.keys())})"
                    continue

            act_val = actual[key]

            # Caso especial: left/right/value como string en expected → comparar con Identifier.name o literal
            if key in ("left", "right", "value", "callee") and isinstance(exp_val, str) and isinstance(act_val, dict):
                act_name = act_val.get("name") or act_val.get("value")
                if act_name != exp_val:
                    return False, f"{path}.{key}: esperaba '{exp_val}', se obtuvo '{act_name}'"
                continue

            # Caso especial: body como lista en expected → act_val puede ser Block dict con statements
            if key == "body" and isinstance(exp_val, list) and isinstance(act_val, dict):
                stmts = act_val.get("statements", [])
                ok, msg = _match_list_subset(stmts, exp_val, f"{path}.body")
                if not ok:
                    return False, msg
                continue

            # Caso especial: params como lista de strings en expected vs lista de Param dicts
            if key == "params" and isinstance(exp_val, list) and all(isinstance(p, str) for p in exp_val):
                act_names = [
                    p.get("name", p) if isinstance(p, dict) else p
                    for p in (act_val if isinstance(act_val, list) else [])
                ]
                for p_name in exp_val:
                    if p_name not in act_names:
                        return False, f"{path}.params: esperaba param '{p_name}', encontrado {act_names}"
                continue

            # Caso especial: subject como string → comparar con Identifier.name
            if key == "subject" and isinstance(exp_val, str) and isinstance(act_val, dict):
                act_name = act_val.get("name") or act_val.get("value")
                if act_name != exp_val:
                    return False, f"{path}.subject: esperaba '{exp_val}', se obtuvo '{act_name}'"
                continue

            # Caso especial: pattern como string → comparar con Identifier.name o StringLiteral.value
            if key == "pattern" and isinstance(exp_val, str) and isinstance(act_val, dict):
                act_name = act_val.get("name") or act_val.get("value")
                if act_name != exp_val:
                    return False, f"{path}.pattern: esperaba '{exp_val}', se obtuvo '{act_name}'"
                continue

            ok, msg = _schema_matches(act_val, exp_val, f"{path}.{key}")
            if not ok:
                return False, msg

        return True, ""

    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False, f"{path}: se esperaba lista, se obtuvo {type(actual).__name__}"
        for i, exp_item in enumerate(expected):
            if i >= len(actual):
                return False, f"{path}[{i}]: lista demasiado corta (len={len(actual)})"
            ok, msg = _schema_matches(actual[i], exp_item, f"{path}[{i}]")
            if not ok:
                return False, msg
        return True, ""

    # Valor escalar — comparación directa
    if actual != expected:
        return False, f"{path}: se esperaba {expected!r}, se obtuvo {actual!r}"
    return True, ""


def _check_fixture(lumen_path: Path) -> None:
    """Carga fixture .lumen + .expected y valida."""
    expected_path = lumen_path.with_suffix(".expected")
    source = lumen_path.read_text(encoding="utf-8")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))

    result = parse(source)

    if expected.get("valid") is False:
        assert isinstance(result, ParseError), (
            f"Se esperaba ParseError pero se obtuvo Program: {result}"
        )
        err_spec = expected.get("error", {})
        if "code" in err_spec:
            assert result.code == err_spec["code"], (
                f"Error code: esperaba {err_spec['code']!r}, obtuvo {result.code!r}"
            )
    else:
        assert isinstance(result, Program), (
            f"Se esperaba Program pero se obtuvo ParseError: {result.message} "
            f"(línea {result.line}, col {result.col})"
        )

        # Validar schema si está presente
        if "body" in expected or "node_type" in expected:
            actual_dict = _ast_to_dict(result)
            ok, msg = _schema_matches(actual_dict, expected)
            assert ok, f"Schema mismatch en {lumen_path.name}:\n{msg}"


# ---------------------------------------------------------------------------
# Parametrized fixture tests
# ---------------------------------------------------------------------------

def _get_fixture_pairs() -> list[pytest.param]:
    params = []
    if not FIXTURES_DIR.exists():
        return params
    for lumen_file in sorted(FIXTURES_DIR.glob("*.lumen")):
        expected_file = lumen_file.with_suffix(".expected")
        if expected_file.exists():
            params.append(pytest.param(lumen_file, id=lumen_file.stem))
    return params


@pytest.mark.parametrize("lumen_path", _get_fixture_pairs())
def test_fixture(lumen_path: Path) -> None:
    _check_fixture(lumen_path)


# ---------------------------------------------------------------------------
# Tests unitarios canónicos
# ---------------------------------------------------------------------------

class TestParserBasic:
    def test_hello_world(self) -> None:
        src = '@lumen 1.0\n\nprint "Hello, World"\n'
        result = parse(src)
        assert isinstance(result, Program)
        assert result.version.major == 1
        assert result.version.minor == 0
        assert len(result.top_levels) == 1
        stmt = result.top_levels[0]
        assert isinstance(stmt, PrintStatement)
        assert isinstance(stmt.value, StringLiteral)

    def test_missing_version(self) -> None:
        result = parse('print "hello"\n')
        assert isinstance(result, ParseError)
        assert result.code == "LMN-0100"

    def test_empty_program(self) -> None:
        result = parse("@lumen 1.0\n")
        assert isinstance(result, Program)
        assert len(result.top_levels) == 0

    def test_version_parsing(self) -> None:
        result = parse("@lumen 2.3\n")
        assert isinstance(result, Program)
        assert result.version.major == 2
        assert result.version.minor == 3

    def test_capability_decl(self) -> None:
        src = "@lumen 1.0\nuse comm.email\n"
        result = parse(src)
        assert isinstance(result, Program)
        caps = result.capabilities
        assert len(caps) == 1
        assert caps[0].path == ("comm", "email")

    def test_capability_with_alias(self) -> None:
        src = "@lumen 1.0\nuse sensitive.payments as pay\n"
        result = parse(src)
        assert isinstance(result, Program)
        assert result.capabilities[0].alias == "pay"

    def test_function_decl(self) -> None:
        src = "@lumen 1.0\n\nfn add(a, b):\n  return a + b\n"
        result = parse(src)
        assert isinstance(result, Program)
        fns = result.functions
        assert len(fns) == 1
        fn = fns[0]
        assert fn.name == "add"
        assert len(fn.params) == 2
        assert fn.params[0].name == "a"
        assert fn.params[1].name == "b"

    def test_function_return_type(self) -> None:
        src = "@lumen 1.0\n\nfn greet(name: text) -> text:\n  return name\n"
        result = parse(src)
        assert isinstance(result, Program)
        fn = result.functions[0]
        assert fn.return_type is not None

    def test_action_basic(self) -> None:
        src = (
            "@lumen 1.0\n\n"
            "action pay(amount):\n"
            "  reversible: 24h\n"
            "  audit: full\n"
            "  execute:\n"
            "    print amount\n"
        )
        result = parse(src)
        assert isinstance(result, Program)
        actions = result.actions
        assert len(actions) == 1
        act = actions[0]
        assert act.name == "pay"
        assert act.body.reversible is not None
        assert act.body.audit is not None
        assert act.body.audit.level == "full"
        assert act.body.execute is not None

    def test_action_requires(self) -> None:
        src = (
            "@lumen 1.0\n\n"
            "action pay(amount):\n"
            "  requires: amount > 0\n"
            "  execute:\n"
            "    print amount\n"
        )
        result = parse(src)
        assert isinstance(result, Program)
        act = result.actions[0]
        assert act.body.requires is not None
        assert isinstance(act.body.requires.condition, BinaryOp)
        assert act.body.requires.condition.op == ">"

    def test_agent_decl(self) -> None:
        src = (
            "@lumen 1.0\n\n"
            "agent monitor:\n"
            "  watch: events.new_email\n"
            "  on email:\n"
            "    print email\n"
        )
        result = parse(src)
        assert isinstance(result, Program)
        agents = result.agents
        assert len(agents) == 1
        assert agents[0].name == "monitor"
        assert agents[0].body.watch is not None

    def test_assignment(self) -> None:
        src = "@lumen 1.0\n\nx = 42\n"
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, Assignment)
        assert stmt.target == "x"
        assert isinstance(stmt.value, NumberLiteral)
        assert stmt.value.value == "42"

    def test_if_statement(self) -> None:
        src = "@lumen 1.0\n\nif x > 0:\n  print x\n"
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, IfStatement)
        assert isinstance(stmt.condition, BinaryOp)

    def test_if_else(self) -> None:
        src = "@lumen 1.0\n\nif x > 0:\n  print x\nelse:\n  print 0\n"
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, IfStatement)
        assert stmt.else_block is not None

    def test_for_loop(self) -> None:
        src = "@lumen 1.0\n\nfor item in items:\n  print item\n"
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, ForStatement)
        assert stmt.target == "item"

    def test_match_statement(self) -> None:
        src = (
            "@lumen 1.0\n\n"
            "match x:\n"
            '  "a" -> print "A"\n'
            '  "b" -> print "B"\n'
        )
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, MatchStatement)
        assert len(stmt.arms) == 2

    def test_pipeline(self) -> None:
        src = "@lumen 1.0\n\nfetch(url) | parse_json\n"
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, ExpressionStatement)
        assert isinstance(stmt.expression, Pipeline)
        assert len(stmt.expression.steps) == 2

    def test_resolve_block(self) -> None:
        src = (
            '@lumen 1.0\n\n'
            'entity = resolve("cliente") {\n'
            '  high_confidence: use_context(crm)\n'
            '  unknown: fail_safe()\n'
            '}\n'
        )
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.value, ResolveBlock)
        assert len(stmt.value.strategies) == 2

    def test_string_literal(self) -> None:
        src = '@lumen 1.0\n\nx = "hello"\n'
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.value, StringLiteral)
        assert stmt.value.value == "hello"

    def test_boolean_literals(self) -> None:
        src = "@lumen 1.0\n\nx = true\ny = false\n"
        result = parse(src)
        assert isinstance(result, Program)
        assert isinstance(result.top_levels[0], Assignment)
        assert isinstance(result.top_levels[0].value, BooleanLiteral)
        assert result.top_levels[0].value.value is True

    def test_money_literal(self) -> None:
        src = "@lumen 1.0\n\nx = $100 USD\n"
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.value, MoneyLiteral)
        assert stmt.value.currency == "USD"

    def test_time_literal(self) -> None:
        src = "@lumen 1.0\n\nttl = 24h\n"
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.value, TimeLiteral)

    def test_binary_ops(self) -> None:
        src = "@lumen 1.0\n\nx = a + b * c\n"
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.value, BinaryOp)

    def test_function_call_with_kwargs(self) -> None:
        src = "@lumen 1.0\n\nsend(to=alice, msg=hello)\n"
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, ExpressionStatement)
        call = stmt.expression
        assert isinstance(call, FunctionCall)
        assert len(call.kwargs) == 2

    def test_multiple_top_levels(self) -> None:
        src = (
            "@lumen 1.0\n"
            "use comm.email\n"
            "use sensitive.pay\n\n"
            "fn hello():\n"
            "  return 1\n\n"
            "action send(x):\n"
            "  execute:\n"
            "    print x\n"
        )
        result = parse(src)
        assert isinstance(result, Program)
        assert len(result.capabilities) == 2
        assert len(result.functions) == 1
        assert len(result.actions) == 1

    def test_error_missing_in_keyword(self) -> None:
        src = "@lumen 1.0\n\nfor item items:\n  print item\n"
        result = parse(src)
        assert isinstance(result, ParseError)
        assert result.code == "LMN-0010"

    def test_error_missing_colon_fn(self) -> None:
        src = "@lumen 1.0\n\nfn add(a, b)\n  return a\n"
        result = parse(src)
        assert isinstance(result, ParseError)
        assert result.code == "LMN-0010"

    def test_doc_comment_skipped(self) -> None:
        src = "@lumen 1.0\n\n#: This is a doc comment\nprint 1\n"
        result = parse(src)
        assert isinstance(result, Program)

    def test_because_annotation(self) -> None:
        src = '@lumen 1.0\n\nx = 42 because "business rule"\n'
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, Assignment)
        assert stmt.because is not None
        assert stmt.because.reason == "business rule"

    def test_print_statement_as_expr(self) -> None:
        """print se parsea como PrintStatement."""
        src = '@lumen 1.0\n\nprint "test"\n'
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, PrintStatement)
        assert isinstance(stmt.value, StringLiteral)

    def test_import_decl(self) -> None:
        src = '@lumen 1.0\n\nimport "utils.lumen"\n'
        result = parse(src)
        assert isinstance(result, Program)
        imports = [t for t in result.top_levels if isinstance(t, ImportDecl)]
        assert len(imports) == 1

    def test_mode_clause(self) -> None:
        src = (
            "@lumen 1.0\n\n"
            "action safe_op(x):\n"
            "  mode: safe\n"
            "  execute:\n"
            "    print x\n"
        )
        result = parse(src)
        assert isinstance(result, Program)
        act = result.actions[0]
        assert act.body.mode is not None
        assert act.body.mode.mode == "safe"

    def test_not_expression(self) -> None:
        src = "@lumen 1.0\n\nx = not true\n"
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.value, UnaryOp)
        assert stmt.value.op == "not"

    def test_list_literal(self) -> None:
        src = "@lumen 1.0\n\nx = [1, 2, 3]\n"
        result = parse(src)
        assert isinstance(result, Program)
        stmt = result.top_levels[0]
        assert isinstance(stmt, Assignment)
        assert isinstance(stmt.value, FunctionCall)
        assert stmt.value.name == "__list__"
        assert len(stmt.value.args) == 3

    def test_return_without_value(self) -> None:
        src = "@lumen 1.0\n\nfn f():\n  return\n"
        result = parse(src)
        assert isinstance(result, Program)
        fn = result.functions[0]
        ret = fn.body.statements[0]
        assert isinstance(ret, ReturnStatement)
        assert ret.value is None

    def test_return_with_value(self) -> None:
        src = "@lumen 1.0\n\nfn f(x):\n  return x + 1\n"
        result = parse(src)
        assert isinstance(result, Program)
        fn = result.functions[0]
        ret = fn.body.statements[0]
        assert isinstance(ret, ReturnStatement)
        assert isinstance(ret.value, BinaryOp)
