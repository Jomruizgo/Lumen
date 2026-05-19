"""Pase A.8 — Resolución semántica.

Valida bloques `resolve(...)` y registra información sobre resolución de entidades.
En modo 'safe', cada ResolveBlock debe tener estrategias 'ambiguous' y 'unknown'.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

from lumen.compiler.ast_nodes import (
    ActionDecl,
    AgentDecl,
    Assignment,
    Block,
    ExpressionStatement,
    ForStatement,
    FunctionDecl,
    IfStatement,
    MatchStatement,
    Pipeline,
    PrintStatement,
    Program,
    ResolveBlock,
    ReturnStatement,
    Statement,
    UndoStatement,
)
from lumen.compiler.typechecker import CompileError, TypedProgram


# ---------------------------------------------------------------------------
# Tipo de resultado
# ---------------------------------------------------------------------------

@dataclass
class ResolvedProgram:
    typed: TypedProgram
    # action_name → estrategia de resolución más relevante encontrada
    resolved_entities: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validación de un ResolveBlock individual
# ---------------------------------------------------------------------------

_REQUIRED_SAFE_STRATEGIES: frozenset[str] = frozenset({"ambiguous", "unknown"})


def _validate_resolve_block(
    node: ResolveBlock,
    mode: str,
    context_name: str,
    errors: list[CompileError],
) -> str:
    """Valida un ResolveBlock y retorna la estrategia principal encontrada."""
    strategy_names = {s.name for s in node.strategies}

    if mode == "safe":
        missing = _REQUIRED_SAFE_STRATEGIES - strategy_names
        for missing_name in sorted(missing):  # orden determinista
            errors.append(
                CompileError(
                    code="LMN-0002",
                    message=(
                        f"Bloque 'resolve' en '{context_name}' no tiene estrategia "
                        f"'{missing_name}' (requerida en modo 'safe')"
                    ),
                    line=node.position.line,
                    col=node.position.col,
                )
            )

    # Estrategia principal: preferir high_confidence > ambiguous > unknown > primera disponible
    for preferred in ("high_confidence", "ambiguous", "unknown"):
        if preferred in strategy_names:
            return preferred

    return next(iter(strategy_names), "unknown")


# ---------------------------------------------------------------------------
# Recorrido de statements buscando ResolveBlock
# ---------------------------------------------------------------------------

def _find_resolve_blocks_in_block(block: Block) -> list[ResolveBlock]:
    """Recorre un Block y retorna todos los ResolveBlock encontrados."""
    result: list[ResolveBlock] = []
    for stmt in block.statements:
        result.extend(_find_resolve_blocks_in_stmt(stmt))
    return result


def _find_resolve_blocks_in_stmt(stmt: Statement) -> list[ResolveBlock]:
    result: list[ResolveBlock] = []

    if isinstance(stmt, ResolveBlock):
        result.append(stmt)
        # También buscar en el cuerpo de cada estrategia
        for strategy in stmt.strategies:
            if isinstance(strategy.body, Block):
                result.extend(_find_resolve_blocks_in_block(strategy.body))

    elif isinstance(stmt, IfStatement):
        result.extend(_find_resolve_blocks_in_block(stmt.then_block))
        if stmt.else_block:
            result.extend(_find_resolve_blocks_in_block(stmt.else_block))

    elif isinstance(stmt, ForStatement):
        result.extend(_find_resolve_blocks_in_block(stmt.body))

    elif isinstance(stmt, MatchStatement):
        for arm in stmt.arms:
            if isinstance(arm.body, Block):
                result.extend(_find_resolve_blocks_in_block(arm.body))

    return result


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def resolve_semantics(typed: TypedProgram, mode: str) -> Union[ResolvedProgram, list[CompileError]]:
    """Valida ResolveBlock en el AST y construye el mapa de entidades resueltas.

    En modo 'safe': cada ResolveBlock debe tener estrategias 'ambiguous' y 'unknown'.
    Retorna ResolvedProgram si no hay errores, o list[CompileError] si los hay.
    """
    program = typed.ast
    errors: list[CompileError] = []
    resolved_entities: dict[str, str] = {}

    for tl in program.top_levels:

        if isinstance(tl, ActionDecl):
            context = tl.name
            blocks_to_check: list[ResolveBlock] = []

            if tl.body.execute:
                blocks_to_check.extend(
                    _find_resolve_blocks_in_block(tl.body.execute.body)
                )

            for rb in blocks_to_check:
                strategy = _validate_resolve_block(rb, mode, context, errors)
                # Registrar: la acción usa esta estrategia de resolución
                if context not in resolved_entities:
                    resolved_entities[context] = strategy

        elif isinstance(tl, FunctionDecl):
            context = tl.name
            blocks_to_check = _find_resolve_blocks_in_block(tl.body)

            for rb in blocks_to_check:
                strategy = _validate_resolve_block(rb, mode, context, errors)
                if context not in resolved_entities:
                    resolved_entities[context] = strategy

        elif isinstance(tl, AgentDecl):
            context = tl.name
            for on_clause in tl.body.on_clauses:
                blocks_to_check = _find_resolve_blocks_in_block(on_clause.body)
                for rb in blocks_to_check:
                    strategy = _validate_resolve_block(rb, mode, context, errors)
                    if context not in resolved_entities:
                        resolved_entities[context] = strategy

        elif isinstance(tl, Statement):
            # Statements top-level (infrecuente pero posible)
            for rb in _find_resolve_blocks_in_stmt(tl):
                strategy = _validate_resolve_block(rb, mode, "<top-level>", errors)
                resolved_entities.setdefault("<top-level>", strategy)

    if errors:
        return errors

    return ResolvedProgram(typed=typed, resolved_entities=resolved_entities)
