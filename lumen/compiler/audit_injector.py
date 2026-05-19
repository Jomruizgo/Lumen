"""Pass A.10 — Audit Injector.

Inyecta nodos AuditLogCall en los cuerpos execute de las ActionDecl.

Reglas:
- El nivel de audit se determina:
    1. Si la action tiene `audit:` explícito → usar ese nivel.
    2. Si el modo es "safe"  → "minimal" por defecto.
    3. Si el modo es "fast"  → "silent" por defecto.
    4. Si el modo es "flow"  → "minimal" por defecto.
- Si el nivel es "silent" → no se inyecta nada.
- En cualquier otro caso → prepender un AuditLogCall(event_type="execution")
  antes de los statements existentes.

El AST es frozen (pydantic), por tanto se crean nuevos nodos con model_copy().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from lumen.compiler.ast_nodes import (
    ActionDecl,
    ActionBody,
    AuditLogCall,
    Block,
    ExecuteClause,
    Program,
    SourcePosition,
    TopLevel,
)

# Posición sintética usada para nodos inyectados
_SYNTHETIC_POS = SourcePosition(line=0, col=0, file="<injected>")


# ---------------------------------------------------------------------------
# Tipos de retorno
# ---------------------------------------------------------------------------

@dataclass
class InstrumentedProgram:
    """Resultado del paso de inyección de audit.

    Attributes:
        resolved: El ResolvedProgram proveniente del pass anterior.
        program:  El Program con los AuditLogCall inyectados.
    """
    resolved: Any  # ResolvedProgram del pass anterior (type abierto para evitar import circular)
    program: Program


# ---------------------------------------------------------------------------
# Lógica de determinación de nivel
# ---------------------------------------------------------------------------

def _determine_level(
    action: ActionDecl,
    global_mode: str,
) -> Literal["full", "minimal", "silent"]:
    """Determina el nivel de audit que corresponde a esta action."""
    # 1. Cláusula explícita en la action → máxima prioridad
    if action.body.audit is not None:
        return action.body.audit.level

    # 2. Modo local de la action (si lo tiene)
    local_mode = action.body.mode.mode if action.body.mode is not None else global_mode

    # 3. Mapeo modo → nivel por defecto
    if local_mode == "fast":
        return "silent"
    # safe o flow → minimal
    return "minimal"


# ---------------------------------------------------------------------------
# Inyección en un ActionDecl
# ---------------------------------------------------------------------------

def _inject_into_action(action: ActionDecl, global_mode: str) -> ActionDecl:
    """Retorna un ActionDecl (posiblemente nuevo) con el AuditLogCall inyectado."""
    level = _determine_level(action, global_mode)

    if level == "silent":
        # No inyectar nada
        return action

    execute = action.body.execute
    if execute is None:
        # Sin bloque execute → nada que instrumentar
        return action

    audit_node = AuditLogCall(
        position=_SYNTHETIC_POS,
        action_name=action.name,
        level=level,
        event_type="execution",
        payload=None,
    )

    new_statements = (audit_node,) + execute.body.statements

    new_block = execute.body.model_copy(update={"statements": new_statements})
    new_execute = execute.model_copy(update={"body": new_block})
    new_body = action.body.model_copy(update={"execute": new_execute})
    return action.model_copy(update={"body": new_body})


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def inject_audit(resolved: Any, mode: str) -> InstrumentedProgram:
    """Inyecta AuditLogCall en todas las ActionDecl del programa.

    Args:
        resolved: ResolvedProgram del pass anterior. Se usa para acceder al
                  Program original a través de resolved.typed.ast.
        mode:     Modo global del programa ("fast", "safe", "flow").

    Returns:
        InstrumentedProgram con el program modificado y una referencia al
        resolved original.
    """
    # Obtener el Program original desde el resolved (cadena de wrappers)
    original_program: Program = _extract_program(resolved)

    new_top_levels: list[TopLevel] = []
    for tl in original_program.top_levels:
        if isinstance(tl, ActionDecl):
            new_top_levels.append(_inject_into_action(tl, mode))
        else:
            new_top_levels.append(tl)

    new_program = original_program.model_copy(
        update={"top_levels": tuple(new_top_levels)}
    )

    return InstrumentedProgram(resolved=resolved, program=new_program)


def _extract_program(resolved: Any) -> Program:
    """Navega la cadena resolved → typed → ast para extraer el Program."""
    # Ruta estándar: resolved.typed.ast
    typed = getattr(resolved, "typed", None)
    if typed is not None:
        ast = getattr(typed, "ast", None)
        if isinstance(ast, Program):
            return ast

    # Fallback: si resolved ya es un Program
    if isinstance(resolved, Program):
        return resolved

    # Fallback: atributo directo .program o .ast
    for attr in ("program", "ast"):
        candidate = getattr(resolved, attr, None)
        if isinstance(candidate, Program):
            return candidate

    raise TypeError(
        f"No se pudo extraer un Program desde el objeto resolved de tipo "
        f"{type(resolved).__name__}. Se esperaba resolved.typed.ast → Program."
    )
