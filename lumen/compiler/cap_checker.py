"""Pase A.6 — Verificación de capacidades declaradas.

Valida que toda llamada a capacidad en el AST tenga una declaración `use`
correspondiente. Recorre el AST completo de forma recursiva y recolecta
todos los errores (no para en el primero).

Nota: el parser actual convierte `comm.email(...)` en
  FunctionCall(name="email", args=(DotAccess(obj=Identifier("comm"), field="email"), ...), ...)
Esta pass reconoce ambas representaciones (CapabilityCall y FunctionCall+DotAccess).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generator, Optional

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
    FunctionDecl,
    Identifier,
    IfStatement,
    IndexAccess,
    MatchStatement,
    Pipeline,
    PrintStatement,
    Program,
    ResolveBlock,
    ReturnStatement,
    Statement,
    StringInterpolation,
    UndoStatement,
    UnaryOp,
    Expression,
)


# ---------------------------------------------------------------------------
# Mapa de capacidades stdlib conocidas (para referencia/sugerencias)
# ---------------------------------------------------------------------------

KNOWN_CAPABILITIES: set[str] = {
    "comm.email", "comm.notify", "comm.message",
    "time.now", "time.wait", "time.calendar",
    "data.read", "data.write", "data.parse", "data.search", "data.extract",
    "sensitive.transfer", "sensitive.delete", "sensitive.deploy",
    "cli.run", "cli.pipe",
    "web.fetch", "web.post", "web.webhook",
    "llm.ask", "llm.classify", "llm.extract",
}

# Top-level namespaces that are known to be capability roots (not variable names).
# Calls whose root is NOT in this set AND NOT in declared capabilities are ignored
# (treated as variable method calls, not capability calls).
KNOWN_CAP_ROOTS: frozenset[str] = frozenset({
    "comm", "time", "data", "sensitive", "cli", "web", "llm",
    "read", "send", "notify", "transfer", "audit", "listen",
    "summarize", "filter", "sort_by", "search", "fetch", "post",
})


# ---------------------------------------------------------------------------
# Error compartido (reutilizable entre passes)
# ---------------------------------------------------------------------------

@dataclass
class CompileError:
    code: str       # "LMN-XXXX"
    message: str
    line: int
    col: int


# ---------------------------------------------------------------------------
# Extracción de ruta de capacidad desde nodos de expresión
# ---------------------------------------------------------------------------

def _extract_cap_path(expr: Expression) -> Optional[tuple[str, ...]]:
    """Extrae la ruta de capacidad de un nodo de llamada, si es aplicable.

    Reconoce:
    - CapabilityCall directos
    - FunctionCall cuyo primer arg es DotAccess(Identifier, field)
      (representación del parser para `ns.fn(...)`)
    """
    if isinstance(expr, CapabilityCall):
        return expr.path

    if isinstance(expr, FunctionCall) and expr.args:
        first = expr.args[0]
        if isinstance(first, DotAccess):
            path = _dotaccess_to_path(first)
            if path:
                return path

    return None


def _dotaccess_to_path(da: DotAccess) -> Optional[tuple[str, ...]]:
    """Convierte DotAccess anidado de Identifiers en una tupla de partes."""
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
# Recorrido genérico del AST
# ---------------------------------------------------------------------------

def _walk_expr(expr: Expression) -> Generator[Expression, None, None]:
    """Yield this expression and all descendant expressions."""
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
    elif isinstance(stmt, UndoStatement):
        yield from _walk_expr(stmt.action_id)
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


def _walk_program_exprs(program: Program) -> Generator[Expression, None, None]:
    """Yield all Expression nodes in the entire program."""
    for tl in program.top_levels:
        if isinstance(tl, ActionDecl):
            body = tl.body
            if body.requires:
                yield from _walk_expr(body.requires.condition)
            if body.escalation:
                yield from _walk_expr(body.escalation.target)
            if body.execute:
                yield from _walk_block(body.execute.body)

        elif isinstance(tl, FunctionDecl):
            yield from _walk_block(tl.body)

        elif isinstance(tl, AgentDecl):
            ab = tl.body
            if ab.watch:
                yield from _walk_expr(ab.watch.expression)
            if ab.state:
                for _, _, default in ab.state.fields:
                    if default is not None:
                        yield from _walk_expr(default)
            if ab.schedule:
                yield from _walk_expr(ab.schedule.expression)
            if ab.config:
                for _, val in ab.config.settings:
                    yield from _walk_expr(val)
            for on_clause in ab.on_clauses:
                yield from _walk_expr(on_clause.pattern)
                if on_clause.condition:
                    yield from _walk_expr(on_clause.condition)
                yield from _walk_block(on_clause.body)

        elif isinstance(tl, Statement):
            yield from _walk_stmt(tl)


# ---------------------------------------------------------------------------
# Matching de cobertura de capacidades
# ---------------------------------------------------------------------------

def _is_covered(call_path: tuple[str, ...], declared: list[CapabilityDecl]) -> bool:
    """True si call_path está cubierto por alguna declaración.

    Una declaración ("comm", "email") cubre:
    - llamadas exactas ("comm", "email")
    - llamadas más específicas ("comm", "email", "read")
    """
    for decl in declared:
        dp = decl.path
        if len(dp) <= len(call_path) and call_path[: len(dp)] == dp:
            return True
    return False


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def check_capabilities(program: Program) -> list[CompileError]:
    """Verifica que cada llamada a capacidad tiene declaración `use` correspondiente.

    Reconoce tanto CapabilityCall como FunctionCall+DotAccess (representación
    que produce el parser actual para `namespace.cap(...)`).
    Recolecta todos los errores sin detenerse en el primero.
    """
    declared = program.capabilities
    errors: list[CompileError] = []
    # Evitar reportar el mismo path+posición más de una vez
    seen: set[tuple[tuple[str, ...], int, int]] = set()

    for expr in _walk_program_exprs(program):
        path = _extract_cap_path(expr)
        if path is None:
            continue

        key = (path, expr.position.line, expr.position.col)
        if key in seen:
            continue
        seen.add(key)

        # Skip paths whose root is not a known capability namespace or declared prefix.
        # This prevents variable method calls (e.g. state.x.append()) from being flagged.
        root = path[0] if path else ""
        declared_roots = {d.path[0] for d in declared}
        if root not in KNOWN_CAP_ROOTS and root not in declared_roots:
            continue

        if not _is_covered(path, declared):
            path_str = ".".join(path)
            errors.append(
                CompileError(
                    code="LMN-0001",
                    message=f"Capacidad '{path_str}' no declarada con 'use'",
                    line=expr.position.line,
                    col=expr.position.col,
                )
            )

    return errors
