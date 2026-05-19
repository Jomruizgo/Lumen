"""Pase A.5 — Detección de modo del programa.

Infiere el modo de ejecución ("fast", "safe", "flow") a partir del AST,
aplicando las reglas de prioridad definidas en la especificación de Lumen.

Nota: el parser actual convierte `comm.email(...)` en
  FunctionCall(name="email", args=(DotAccess(obj=Identifier("comm"), field="email"), ...), ...)
en lugar de CapabilityCall. Esta pass maneja ambas representaciones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generator, Literal, Optional, Union

from lumen.compiler.ast_nodes import (
    ActionDecl,
    AgentDecl,
    Assignment,
    BinaryOp,
    Block,
    CapabilityCall,
    CapabilityDecl,
    DotAccess,
    ExpressionStatement,
    ForStatement,
    FunctionCall,
    Identifier,
    IfStatement,
    IndexAccess,
    MatchStatement,
    Pipeline,
    PrintStatement,
    Program,
    ResolveBlock,
    ReturnStatement,
    StringInterpolation,
    UndoStatement,
    UnaryOp,
    Expression,
    Statement,
)


# ---------------------------------------------------------------------------
# Tipos de resultado
# ---------------------------------------------------------------------------

@dataclass
class CompileError:
    code: str       # "LMN-XXXX"
    message: str
    line: int
    col: int


@dataclass
class ModeResult:
    mode: Literal["fast", "safe", "flow"]
    reason: str  # explicación legible para el desarrollador


# ---------------------------------------------------------------------------
# Extracción de ruta de capacidad
# ---------------------------------------------------------------------------

def _extract_cap_path(expr: Expression) -> Optional[tuple[str, ...]]:
    """Extrae la ruta de capacidad de un nodo de llamada, si aplica.

    Maneja tanto CapabilityCall como la representación que el parser produce
    en la práctica: FunctionCall cuyo primer arg es DotAccess(Identifier, field).

    Ejemplos reconocidos:
      - CapabilityCall(path=("comm","email"), ...)  → ("comm", "email")
      - FunctionCall(name="email", args=(DotAccess(Identifier("comm"), "email"), ...), ...)
        → ("comm", "email")
      - FunctionCall con DotAccess anidado: obj.sub.method(...)
        → obj puede ser DotAccess(Identifier("a"), "b"), field="c"
        → ("a", "b", "c")
    """
    if isinstance(expr, CapabilityCall):
        return expr.path

    if isinstance(expr, FunctionCall) and expr.args:
        first = expr.args[0]
        if isinstance(first, DotAccess):
            path = _extract_dotaccess_path(first)
            if path:
                return path

    return None


def _extract_dotaccess_path(da: DotAccess) -> Optional[tuple[str, ...]]:
    """Extrae la ruta completa de un DotAccess anidado de Identifiers."""
    parts: list[str] = [da.field]
    current: Expression = da.obj
    while isinstance(current, DotAccess):
        parts.append(current.field)
        current = current.obj
    if isinstance(current, Identifier):
        parts.append(current.name)
        parts.reverse()
        return tuple(parts)
    return None


# ---------------------------------------------------------------------------
# Helpers de recorrido
# ---------------------------------------------------------------------------

def _walk_expr(expr: Expression) -> Generator[Expression, None, None]:
    """Yield this expr and all sub-expressions recursively."""
    yield expr
    if isinstance(expr, (CapabilityCall, FunctionCall)):
        for arg in expr.args:
            yield from _walk_expr(arg)
        for _, v in expr.kwargs:
            yield from _walk_expr(v)
    elif isinstance(expr, BinaryOp):
        yield from _walk_expr(expr.left)
        yield from _walk_expr(expr.right)
    elif isinstance(expr, UnaryOp):
        yield from _walk_expr(expr.operand)
    elif isinstance(expr, DotAccess):
        yield from _walk_expr(expr.obj)
    elif isinstance(expr, IndexAccess):
        yield from _walk_expr(expr.obj)
        yield from _walk_expr(expr.index)
    elif isinstance(expr, StringInterpolation):
        for part in expr.parts:
            if not isinstance(part, str):
                yield from _walk_expr(part)


def _walk_block(block: Block) -> Generator[Expression, None, None]:
    for stmt in block.statements:
        yield from _walk_stmt(stmt)


def _walk_stmt(stmt: Statement) -> Generator[Expression, None, None]:
    if isinstance(stmt, Assignment):
        yield from _walk_expr(stmt.value)
    elif isinstance(stmt, ExpressionStatement):
        yield from _walk_expr(stmt.expression)
    elif isinstance(stmt, ReturnStatement) and stmt.value is not None:
        yield from _walk_expr(stmt.value)
    elif isinstance(stmt, PrintStatement):
        yield from _walk_expr(stmt.value)
    elif isinstance(stmt, Pipeline):
        for step in stmt.steps:
            yield from _walk_expr(step)
    elif isinstance(stmt, IfStatement):
        yield from _walk_expr(stmt.condition)
        yield from _walk_block(stmt.then_block)
        if stmt.else_block:
            yield from _walk_block(stmt.else_block)
    elif isinstance(stmt, ForStatement):
        yield from _walk_expr(stmt.iterable)
        yield from _walk_block(stmt.body)
    elif isinstance(stmt, MatchStatement):
        yield from _walk_expr(stmt.subject)
        for arm in stmt.arms:
            if isinstance(arm.body, Block):
                yield from _walk_block(arm.body)
            else:
                yield from _walk_expr(arm.body)
    elif isinstance(stmt, ResolveBlock):
        yield from _walk_expr(stmt.subject)
        for strategy in stmt.strategies:
            if isinstance(strategy.body, Block):
                yield from _walk_block(strategy.body)
            else:
                yield from _walk_expr(strategy.body)
    elif isinstance(stmt, UndoStatement):
        yield from _walk_expr(stmt.action_id)


def _iter_cap_paths_in_action(action: ActionDecl) -> Generator[tuple[str, ...], None, None]:
    """Yield capability paths for every capability call found in an ActionDecl."""
    sources: list[Generator[Expression, None, None]] = []
    if action.body.execute:
        sources.append(_walk_block(action.body.execute.body))
    if action.body.requires:
        sources.append(_walk_expr(action.body.requires.condition))
    if action.body.escalation:
        sources.append(_walk_expr(action.body.escalation.target))

    for gen in sources:
        for expr in gen:
            path = _extract_cap_path(expr)
            if path:
                yield path


def _uses_sensitive(action: ActionDecl) -> bool:
    """True if this action references any sensitive.* capability."""
    for path in _iter_cap_paths_in_action(action):
        if path and path[0] == "sensitive":
            return True
    return False


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def detect_mode(program: Program) -> Union[ModeResult, CompileError]:
    """Infiere el modo del programa a partir del AST.

    Reglas (en orden de prioridad):
    1. mode: fast + sensitive.* → error LMN-0040
    2. AgentDecl presente → "flow"
    3. CapabilityDecl sensitive.* → "safe"
    4. ActionDecl con escalation → "safe"
    5. ActionDecl con audit: full → "safe"
    6. Fallback → "fast"
    """
    # Regla 1: fast + sensitive.* es un error de seguridad
    for action in program.actions:
        if action.body.mode and action.body.mode.mode == "fast":
            if _uses_sensitive(action):
                return CompileError(
                    code="LMN-0040",
                    message=(
                        f"La acción '{action.name}' está marcada como 'fast' "
                        "pero llama a capacidades sensibles (sensitive.*). "
                        "Las capacidades sensibles requieren modo 'safe'."
                    ),
                    line=action.body.mode.position.line,
                    col=action.body.mode.position.col,
                )

    # Regla 2: agent implica flow
    if program.agents:
        agent_name = program.agents[0].name
        return ModeResult(
            mode="flow",
            reason=f"Programa contiene agente '{agent_name}'; el modo es 'flow'.",
        )

    # Regla 3: capacidad sensitive.* declarada con use implica safe
    for cap in program.capabilities:
        if cap.path and cap.path[0] == "sensitive":
            return ModeResult(
                mode="safe",
                reason=(
                    f"Capacidad sensible '{cap.path_str}' declarada con 'use'; "
                    "el modo es 'safe'."
                ),
            )

    # Regla 4: escalation implica safe
    for action in program.actions:
        if action.body.escalation:
            return ModeResult(
                mode="safe",
                reason=(
                    f"La acción '{action.name}' tiene cláusula 'escalation'; "
                    "el modo es 'safe'."
                ),
            )

    # Regla 5: audit: full implica safe
    for action in program.actions:
        if action.body.audit and action.body.audit.level == "full":
            return ModeResult(
                mode="safe",
                reason=(
                    f"La acción '{action.name}' tiene 'audit: full'; "
                    "el modo es 'safe'."
                ),
            )

    # Regla 6: fallback
    return ModeResult(mode="fast", reason="Sin indicios de 'safe' o 'flow'; modo es 'fast'.")
