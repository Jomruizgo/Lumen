"""Pass A.9 — Reversibility Checker.

Valida que las actions que usan capacidades irreversibles declaren `reversible:`
explícitamente. También emite advertencias cuando se usa modo fast con sensitive.*.

Errores:
  LMN-0003 — CapabilityCall irreversible sin cláusula reversible:
  LMN-0040 — Uso de sensitive.* en modo fast (advertencia, registrada como error)

Nota sobre el AST: el parser produce dos representaciones para una llamada a
capacidad como `sensitive.transfer(amount=x)`:
  - CapabilityCall(path=("sensitive","transfer"), ...)  [si el resolver lo transforma]
  - FunctionCall(name="transfer", args=(DotAccess(Identifier("sensitive"), "transfer"), ...))
    [forma directa del parser, antes del resolver]

Este pass reconoce ambas formas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from lumen.compiler.ast_nodes import (
    ActionDecl,
    Assignment,
    AuditLogCall,
    Block,
    CapabilityCall,
    DotAccess,
    ExpressionStatement,
    Expression,
    ForStatement,
    FunctionCall,
    Identifier,
    IfStatement,
    MatchStatement,
    MatchArm,
    OnClause,
    Pipeline,
    Program,
    ResolveBlock,
    SourcePosition,
    Statement,
    StrategyClause,
)


# ---------------------------------------------------------------------------
# Capacidades irreversibles — prefijos
# ---------------------------------------------------------------------------

IRREVERSIBLE_CAPS: frozenset[str] = frozenset({
    "sensitive.transfer",
    "sensitive.delete",
    "sensitive.deploy",
})


@dataclass
class CompileError:
    code: str        # "LMN-XXXX"
    message: str
    line: int
    col: int


# ---------------------------------------------------------------------------
# Helpers de walk
# ---------------------------------------------------------------------------

def _starts_with_irreversible(path: tuple[str, ...]) -> bool:
    """Retorna True si la ruta de la capacidad empieza con algún prefijo irreversible."""
    joined = ".".join(path)
    return any(joined == prefix or joined.startswith(prefix + ".") for prefix in IRREVERSIBLE_CAPS)


def _is_sensitive(path: tuple[str, ...]) -> bool:
    """Retorna True si la ruta empieza con 'sensitive'."""
    return len(path) > 0 and path[0] == "sensitive"


def _dot_access_path(node: Expression) -> tuple[str, ...] | None:
    """Extrae la ruta de puntos de un nodo DotAccess anidado.

    Ej: DotAccess(DotAccess(Identifier('sensitive'), 'transfer'), 'wire')
        → ('sensitive', 'transfer', 'wire')

    Retorna None si el nodo no es DotAccess/Identifier.
    """
    parts: list[str] = []

    def walk(n: Expression) -> bool:
        if isinstance(n, Identifier):
            parts.append(n.name)
            return True
        if isinstance(n, DotAccess):
            if not walk(n.obj):
                return False
            parts.append(n.field)
            return True
        return False

    if walk(node):
        return tuple(parts)
    return None


# Tipo sintético que representa una llamada de capacidad detectada
@dataclass
class _CapRef:
    """Referencia a una llamada de capacidad (CapabilityCall real o FunctionCall dotted)."""
    path: tuple[str, ...]
    position: SourcePosition


def _collect_cap_refs_from_expr(expr: Expression) -> list[_CapRef]:
    """Recorre una expresión y recoge todas las referencias a capacidades.

    Reconoce dos formas:
    1. CapabilityCall(path=...) — producido por el resolver.
    2. FunctionCall cuyo primer arg es DotAccess — forma directa del parser.
       Ej: sensitive.transfer(amount=x) →
           FunctionCall(name='transfer', args=(DotAccess(Identifier('sensitive'), 'transfer'), ...), ...)
    """
    results: list[_CapRef] = []

    # Forma 1: CapabilityCall explícito (tras el resolver)
    if isinstance(expr, CapabilityCall):
        results.append(_CapRef(path=expr.path, position=expr.position))

    # Forma 2: FunctionCall con DotAccess como primer arg (parser directo)
    elif isinstance(expr, FunctionCall) and expr.args:
        first_arg = expr.args[0]
        if isinstance(first_arg, DotAccess):
            path = _dot_access_path(first_arg)
            if path is not None and len(path) >= 2:
                # Verificar que la ruta tiene pinta de capacidad dotted
                # (empieza con identificador conocido o es sensitive.*)
                results.append(_CapRef(path=path, position=expr.position))
            # Seguir procesando el resto de los args (excluyendo el primero que es el receptor)
            for child in expr.args[1:]:
                results.extend(_collect_cap_refs_from_expr(child))
        else:
            # FunctionCall normal — recorrer todos los args
            for child in expr.args:
                results.extend(_collect_cap_refs_from_expr(child))

        for _k, v in expr.kwargs:
            results.extend(_collect_cap_refs_from_expr(v))
        return results

    # Recorrer sub-expresiones conocidas
    for attr in ("left", "right", "operand", "index"):
        sub = getattr(expr, attr, None)
        if isinstance(sub, Expression):
            results.extend(_collect_cap_refs_from_expr(sub))

    # obj de DotAccess — solo recorrer si el propio DotAccess no era el receiver de un FunctionCall
    if isinstance(expr, DotAccess):
        results.extend(_collect_cap_refs_from_expr(expr.obj))

    if not isinstance(expr, FunctionCall):
        args = getattr(expr, "args", ())
        for child in args:
            if isinstance(child, Expression):
                results.extend(_collect_cap_refs_from_expr(child))

        kwargs = getattr(expr, "kwargs", ())
        for _k, v in kwargs:
            if isinstance(v, Expression):
                results.extend(_collect_cap_refs_from_expr(v))

    if hasattr(expr, "parts"):
        for part in expr.parts:
            if isinstance(part, Expression):
                results.extend(_collect_cap_refs_from_expr(part))

    return results


def _collect_cap_refs_from_block(block: Block) -> list[_CapRef]:
    """Recorre un bloque de statements recursivamente y recoge referencias a capacidades."""
    results: list[_CapRef] = []
    for stmt in block.statements:
        results.extend(_collect_cap_refs_from_stmt(stmt))
    return results


def _collect_cap_refs_from_stmt(stmt: Statement) -> list[_CapRef]:
    """Recorre un statement recursivamente y recoge referencias a capacidades."""
    results: list[_CapRef] = []

    if isinstance(stmt, ExpressionStatement):
        results.extend(_collect_cap_refs_from_expr(stmt.expression))

    elif isinstance(stmt, Assignment):
        results.extend(_collect_cap_refs_from_expr(stmt.value))

    elif isinstance(stmt, Pipeline):
        for step in stmt.steps:
            results.extend(_collect_cap_refs_from_expr(step))

    elif isinstance(stmt, IfStatement):
        results.extend(_collect_cap_refs_from_expr(stmt.condition))
        results.extend(_collect_cap_refs_from_block(stmt.then_block))
        if stmt.else_block is not None:
            results.extend(_collect_cap_refs_from_block(stmt.else_block))

    elif isinstance(stmt, ForStatement):
        results.extend(_collect_cap_refs_from_expr(stmt.iterable))
        results.extend(_collect_cap_refs_from_block(stmt.body))

    elif isinstance(stmt, MatchStatement):
        results.extend(_collect_cap_refs_from_expr(stmt.subject))
        for arm in stmt.arms:
            if isinstance(arm, MatchArm):
                results.extend(_collect_cap_refs_from_expr(arm.pattern))
                if isinstance(arm.body, Block):
                    results.extend(_collect_cap_refs_from_block(arm.body))
                elif isinstance(arm.body, Expression):
                    results.extend(_collect_cap_refs_from_expr(arm.body))

    elif isinstance(stmt, ResolveBlock):
        results.extend(_collect_cap_refs_from_expr(stmt.subject))
        for strategy in stmt.strategies:
            if isinstance(strategy, StrategyClause):
                if isinstance(strategy.body, Block):
                    results.extend(_collect_cap_refs_from_block(strategy.body))
                elif isinstance(strategy.body, Expression):
                    results.extend(_collect_cap_refs_from_expr(strategy.body))

    elif isinstance(stmt, AuditLogCall):
        # Nodo sintético inyectado — puede tener payload expression
        if stmt.payload is not None:
            results.extend(_collect_cap_refs_from_expr(stmt.payload))

    # Statements de tipo OnClause (dentro de agents, si se les pasa)
    elif isinstance(stmt, OnClause):
        results.extend(_collect_cap_refs_from_block(stmt.body))

    # Fallback: intentar extraer cualquier expresión del nodo
    else:
        for attr in ("value", "expression", "condition", "action_id"):
            child = getattr(stmt, attr, None)
            if isinstance(child, Expression):
                results.extend(_collect_cap_refs_from_expr(child))

    return results


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def check_reversibility(program: Program) -> list[CompileError]:
    """Valida que las actions con capacidades irreversibles declaren reversible:.

    Recorre cada ActionDecl del programa y, si su cuerpo de ejecución contiene
    alguna CapabilityCall con prefijo irreversible, exige que exista una
    ReversibleClause. Acumula todos los errores encontrados.

    También emite LMN-0040 si la action usa sensitive.* y su modo es "fast".
    """
    errors: list[CompileError] = []

    for action in program.actions:
        _check_action(action, errors)

    return errors


def _check_action(action: ActionDecl, errors: list[CompileError]) -> None:
    execute = action.body.execute
    if execute is None:
        # Sin bloque execute — nada que verificar
        return

    cap_refs = _collect_cap_refs_from_block(execute.body)
    if not cap_refs:
        return

    action_mode: str | None = None
    if action.body.mode is not None:
        action_mode = action.body.mode.mode

    has_reversible = action.body.reversible is not None

    # Evitar emitir el mismo error LMN-0003 más de una vez por action
    # (si hay múltiples llamadas a irreversibles, reportar la primera de cada una)
    reported_irreversible: set[str] = set()

    for cap_ref in cap_refs:
        cap_path = ".".join(cap_ref.path)

        # --- LMN-0003: capacidad irreversible sin reversible: ---
        if _starts_with_irreversible(cap_ref.path):
            if not has_reversible and cap_path not in reported_irreversible:
                reported_irreversible.add(cap_path)
                errors.append(
                    CompileError(
                        code="LMN-0003",
                        message=(
                            f"La action '{action.name}' llama a '{cap_path}' "
                            f"(capacidad irreversible) pero no declara 'reversible:'. "
                            f"Agregue 'reversible: true', 'reversible: false' o "
                            f"'reversible: <duración>' para ser explícito sobre "
                            f"la política de deshacer."
                        ),
                        line=cap_ref.position.line,
                        col=cap_ref.position.col,
                    )
                )

        # --- LMN-0040: sensitive.* en modo fast ---
        if _is_sensitive(cap_ref.path) and action_mode == "fast":
            errors.append(
                CompileError(
                    code="LMN-0040",
                    message=(
                        f"La action '{action.name}' usa '{cap_path}' (operación sensible) "
                        f"en modo 'fast'. El modo 'fast' omite salvaguardas de seguridad; "
                        f"considera usar 'mode: safe' para operaciones sensitive.*."
                    ),
                    line=cap_ref.position.line,
                    col=cap_ref.position.col,
                )
            )
