"""Pase A.7 — Inferencia de tipos y comprobación básica.

No implementa Hindley-Milner completo; sólo las reglas necesarias para
emitir LMN-0020 (constante sin anotación 'because' en modo safe) y
LMN-0030 (tipos incompatibles en operación binaria).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

from lumen.compiler.ast_nodes import (
    ActionDecl,
    AgentDecl,
    Assignment,
    BinaryOp,
    Block,
    BooleanLiteral,
    CapabilityCall,
    DotAccess,
    ExpressionStatement,
    ForStatement,
    FunctionCall,
    FunctionDecl,
    Identifier,
    IfStatement,
    IndexAccess,
    MatchStatement,
    MoneyLiteral,
    NumberLiteral,
    Pipeline,
    PrintStatement,
    Program,
    ResolveBlock,
    ReturnStatement,
    Statement,
    StringInterpolation,
    StringLiteral,
    TimeLiteral,
    UndoStatement,
    UnaryOp,
    Expression,
)


# ---------------------------------------------------------------------------
# Tipos de resultado
# ---------------------------------------------------------------------------

@dataclass
class CompileError:
    code: str
    message: str
    line: int
    col: int


@dataclass
class TypedProgram:
    ast: Program
    types: dict[str, str]  # identifier name → type string


# ---------------------------------------------------------------------------
# Operadores de comparación
# ---------------------------------------------------------------------------

_COMPARISON_OPS: frozenset[str] = frozenset({"<", ">", "<=", ">=", "==", "!=", "in"})


# ---------------------------------------------------------------------------
# Inferencia de tipo de expresión
# ---------------------------------------------------------------------------

def _infer(expr: Expression, env: dict[str, str]) -> Union[str, CompileError]:
    """Retorna el tipo inferido de expr, o CompileError si hay incompatibilidad."""

    if isinstance(expr, NumberLiteral):
        return "number"

    if isinstance(expr, StringLiteral):
        return "text"

    if isinstance(expr, BooleanLiteral):
        return "boolean"

    if isinstance(expr, TimeLiteral):
        return "time"

    if isinstance(expr, MoneyLiteral):
        return f"Money<{expr.currency}>"

    if isinstance(expr, Identifier):
        return env.get(expr.name, "any")

    if isinstance(expr, FunctionCall):
        return "any"

    if isinstance(expr, CapabilityCall):
        return "any"

    if isinstance(expr, StringInterpolation):
        return "text"

    if isinstance(expr, DotAccess):
        return "any"

    if isinstance(expr, IndexAccess):
        return "any"

    if isinstance(expr, UnaryOp):
        if expr.op == "not":
            return "boolean"
        # negación numérica u otras
        inner = _infer(expr.operand, env)
        if isinstance(inner, CompileError):
            return inner
        return inner

    if isinstance(expr, BinaryOp):
        return _infer_binary(expr, env)

    # Fallback para nodos no cubiertos explícitamente
    return "any"


def _infer_binary(expr: BinaryOp, env: dict[str, str]) -> Union[str, CompileError]:
    op = expr.op

    # Comparadores siempre producen boolean (sin importar operandos)
    if op in _COMPARISON_OPS:
        return "boolean"

    # Operadores lógicos
    if op in ("and", "or"):
        return "boolean"

    left_t = _infer(expr.left, env)
    if isinstance(left_t, CompileError):
        return left_t
    right_t = _infer(expr.right, env)
    if isinstance(right_t, CompileError):
        return right_t

    pos = expr.position

    if op == "+":
        if left_t == "number" and right_t == "number":
            return "number"
        if left_t == "text" and right_t == "text":
            return "text"
        # Money<X> + Money<X>
        if left_t.startswith("Money<") and right_t.startswith("Money<"):
            if left_t == right_t:
                return left_t
            return CompileError(
                code="LMN-0030",
                message=f"No se puede sumar {left_t} y {right_t}: monedas distintas",
                line=pos.line,
                col=pos.col,
            )
        # Si alguno es "any", permitir
        if "any" in (left_t, right_t):
            return "any"
        return CompileError(
            code="LMN-0030",
            message=f"Tipos incompatibles en '+': {left_t} y {right_t}",
            line=pos.line,
            col=pos.col,
        )

    if op == "-":
        if left_t == "number" and right_t == "number":
            return "number"
        if left_t.startswith("Money<") and right_t.startswith("Money<"):
            if left_t == right_t:
                return left_t
            return CompileError(
                code="LMN-0030",
                message=f"No se puede restar {left_t} y {right_t}: monedas distintas",
                line=pos.line,
                col=pos.col,
            )
        if "any" in (left_t, right_t):
            return "any"
        return CompileError(
            code="LMN-0030",
            message=f"Tipos incompatibles en '-': {left_t} y {right_t}",
            line=pos.line,
            col=pos.col,
        )

    if op in ("*", "/"):
        if left_t == "number" and right_t == "number":
            return "number"
        # Money<X> * number
        if left_t.startswith("Money<") and right_t == "number":
            return left_t
        if op == "*" and right_t.startswith("Money<") and left_t == "number":
            return right_t
        if "any" in (left_t, right_t):
            return "any"
        return CompileError(
            code="LMN-0030",
            message=f"Tipos incompatibles en '{op}': {left_t} y {right_t}",
            line=pos.line,
            col=pos.col,
        )

    # Operador desconocido — permisivo
    return "any"


# ---------------------------------------------------------------------------
# Chequeo de statements
# ---------------------------------------------------------------------------

def _check_block(
    block: Block,
    env: dict[str, str],
    mode: str,
    errors: list[CompileError],
) -> None:
    for stmt in block.statements:
        _check_stmt(stmt, env, mode, errors)


def _check_stmt(
    stmt: Statement,
    env: dict[str, str],
    mode: str,
    errors: list[CompileError],
) -> None:
    if isinstance(stmt, Assignment):
        val_type = _infer(stmt.value, env)
        if isinstance(val_type, CompileError):
            errors.append(val_type)
            val_type = "any"

        # LMN-0020: constante literal sin 'because' en modo safe
        if mode == "safe" and stmt.because is None:
            if isinstance(stmt.value, (NumberLiteral, StringLiteral)):
                errors.append(
                    CompileError(
                        code="LMN-0020",
                        message=(
                            f"Asignación de constante literal a '{stmt.target}' "
                            "sin anotación 'because' en modo safe"
                        ),
                        line=stmt.position.line,
                        col=stmt.position.col,
                    )
                )

        env[stmt.target] = val_type

    elif isinstance(stmt, ExpressionStatement):
        result = _infer(stmt.expression, env)
        if isinstance(result, CompileError):
            errors.append(result)

    elif isinstance(stmt, ReturnStatement) and stmt.value is not None:
        result = _infer(stmt.value, env)
        if isinstance(result, CompileError):
            errors.append(result)

    elif isinstance(stmt, PrintStatement):
        result = _infer(stmt.value, env)
        if isinstance(result, CompileError):
            errors.append(result)

    elif isinstance(stmt, Pipeline):
        for step in stmt.steps:
            result = _infer(step, env)
            if isinstance(result, CompileError):
                errors.append(result)

    elif isinstance(stmt, IfStatement):
        cond_t = _infer(stmt.condition, env)
        if isinstance(cond_t, CompileError):
            errors.append(cond_t)
        _check_block(stmt.then_block, dict(env), mode, errors)
        if stmt.else_block:
            _check_block(stmt.else_block, dict(env), mode, errors)

    elif isinstance(stmt, ForStatement):
        iter_t = _infer(stmt.iterable, env)
        if isinstance(iter_t, CompileError):
            errors.append(iter_t)
        inner_env = dict(env)
        inner_env[stmt.target] = "any"
        _check_block(stmt.body, inner_env, mode, errors)

    elif isinstance(stmt, MatchStatement):
        subj_t = _infer(stmt.subject, env)
        if isinstance(subj_t, CompileError):
            errors.append(subj_t)
        for arm in stmt.arms:
            pat_t = _infer(arm.pattern, env)
            if isinstance(pat_t, CompileError):
                errors.append(pat_t)
            if isinstance(arm.body, Block):
                _check_block(arm.body, dict(env), mode, errors)
            else:
                body_t = _infer(arm.body, env)
                if isinstance(body_t, CompileError):
                    errors.append(body_t)

    elif isinstance(stmt, ResolveBlock):
        subj_t = _infer(stmt.subject, env)
        if isinstance(subj_t, CompileError):
            errors.append(subj_t)
        for strategy in stmt.strategies:
            if isinstance(strategy.body, Block):
                _check_block(strategy.body, dict(env), mode, errors)
            else:
                body_t = _infer(strategy.body, env)
                if isinstance(body_t, CompileError):
                    errors.append(body_t)

    elif isinstance(stmt, UndoStatement):
        result = _infer(stmt.action_id, env)
        if isinstance(result, CompileError):
            errors.append(result)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def typecheck(program: Program, mode: str) -> Union[TypedProgram, list[CompileError]]:
    """Realiza inferencia de tipos y emite errores LMN-0020 / LMN-0030.

    Retorna TypedProgram si no hay errores, o list[CompileError] si los hay.
    """
    errors: list[CompileError] = []
    global_env: dict[str, str] = {}

    # Registrar parámetros de funciones y acciones en un entorno global vacío
    # (cada declaración crea su propio entorno local al procesarse)

    for tl in program.top_levels:

        if isinstance(tl, FunctionDecl):
            local_env = dict(global_env)
            for param in tl.params:
                local_env[param.name] = "any"
            _check_block(tl.body, local_env, mode, errors)
            # Exportar la función al env global como "any"
            global_env[tl.name] = "any"

        elif isinstance(tl, ActionDecl):
            local_env = dict(global_env)
            for param in tl.params:
                local_env[param.name] = "any"
            body = tl.body
            if body.requires:
                result = _infer(body.requires.condition, local_env)
                if isinstance(result, CompileError):
                    errors.append(result)
            if body.escalation:
                result = _infer(body.escalation.target, local_env)
                if isinstance(result, CompileError):
                    errors.append(result)
            if body.execute:
                _check_block(body.execute.body, local_env, mode, errors)

        elif isinstance(tl, AgentDecl):
            local_env = dict(global_env)
            agent_body = tl.body
            if agent_body.watch:
                result = _infer(agent_body.watch.expression, local_env)
                if isinstance(result, CompileError):
                    errors.append(result)
            if agent_body.state:
                for fname, _, fdefault in agent_body.state.fields:
                    if fdefault is not None:
                        ftype = _infer(fdefault, local_env)
                        if isinstance(ftype, CompileError):
                            errors.append(ftype)
                            local_env[fname] = "any"
                        else:
                            local_env[fname] = ftype
                    else:
                        local_env[fname] = "any"
            for on_clause in agent_body.on_clauses:
                clause_env = dict(local_env)
                if on_clause.condition:
                    result = _infer(on_clause.condition, clause_env)
                    if isinstance(result, CompileError):
                        errors.append(result)
                _check_block(on_clause.body, clause_env, mode, errors)

        elif isinstance(tl, Assignment):
            # Asignación top-level
            _check_stmt(tl, global_env, mode, errors)

        elif isinstance(tl, Statement):
            _check_stmt(tl, global_env, mode, errors)

    if errors:
        return errors

    return TypedProgram(ast=program, types=dict(global_env))
