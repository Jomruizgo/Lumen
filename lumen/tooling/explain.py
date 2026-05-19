"""Explain mode: descripción en lenguaje natural de un programa Lumen."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ProgramExplanation:
    mode: str
    capabilities: list[str]
    actions: list[str]
    agents: list[str]
    reversible_ops: list[str]
    irreversible_ops: list[str]
    suggestions: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"Modo detectado: {self.mode.upper()}",
            "",
            f"Capacidades usadas ({len(self.capabilities)}):",
        ]
        for cap in self.capabilities:
            lines.append(f"  - {cap}")

        if self.actions:
            lines.append("")
            lines.append(f"Actions definidas ({len(self.actions)}):")
            for action in self.actions:
                lines.append(f"  - {action}")

        if self.agents:
            lines.append("")
            lines.append(f"Agents definidos ({len(self.agents)}):")
            for agent in self.agents:
                lines.append(f"  - {agent}")

        if self.reversible_ops:
            lines.append("")
            lines.append("Operaciones reversibles:")
            for op in self.reversible_ops:
                lines.append(f"  - {op}")

        if self.irreversible_ops:
            lines.append("")
            lines.append("Operaciones IRREVERSIBLES:")
            for op in self.irreversible_ops:
                lines.append(f"  ! {op}")

        if self.suggestions:
            lines.append("")
            lines.append("Sugerencias:")
            for s in self.suggestions:
                lines.append(f"  * {s}")

        return "\n".join(lines)


def explain(source: str) -> ProgramExplanation:
    """Analiza un programa Lumen y retorna explicación en lenguaje natural.

    Usa el compilador real cuando disponible; regex como fallback.
    """
    try:
        return _explain_via_compiler(source)
    except Exception:
        return _explain_via_regex(source)


def _explain_via_compiler(source: str) -> ProgramExplanation:
    from lumen.compiler.pipeline import compile_source
    from lumen.compiler.ast_nodes import (
        ActionDecl, AgentDecl, CapabilityDecl, CapabilityCall,
        ReversibleClause,
    )

    result = compile_source(source)
    if not result.ok or result.program is None:
        raise RuntimeError("Compilation failed")

    program = result.program.instrumented.resolved.typed.ast
    mode = result.program.mode

    capabilities = [cap.path_str for cap in program.capabilities]
    actions = [a.name for a in program.actions]
    agents = [ag.name for ag in program.agents]

    reversible_ops: list[str] = []
    irreversible_ops: list[str] = []

    IRREVERSIBLE_PREFIXES = ("sensitive.transfer", "sensitive.delete", "sensitive.deploy")

    for action in program.actions:
        rev = action.body.reversible
        if rev is not None:
            val = rev.value
            if val is False:
                irreversible_ops.append(f"action {action.name}")
            else:
                reversible_ops.append(f"action {action.name} (ventana: {val})")
        # detect sensitive caps
        if action.body.execute:
            caps_used = _collect_cap_calls(action.body.execute.body)
            for cap_path in caps_used:
                if any(cap_path.startswith(p) for p in IRREVERSIBLE_PREFIXES):
                    if f"action {action.name}" not in irreversible_ops:
                        irreversible_ops.append(f"action {action.name} → {cap_path}")

    suggestions = _generate_suggestions(source, mode, capabilities)

    return ProgramExplanation(
        mode=mode,
        capabilities=capabilities,
        actions=actions,
        agents=agents,
        reversible_ops=reversible_ops,
        irreversible_ops=irreversible_ops,
        suggestions=suggestions,
    )


def _collect_cap_calls(block: object) -> list[str]:
    """Recursively collect CapabilityCall path strings from a Block."""
    from lumen.compiler.ast_nodes import CapabilityCall, Block, IfStatement, ForStatement

    results: list[str] = []
    statements = getattr(block, "statements", [])
    for stmt in statements:
        if type(stmt).__name__ == "CapabilityCall":
            results.append(".".join(stmt.path))
        elif type(stmt).__name__ == "ExpressionStatement":
            expr = getattr(stmt, "expression", None)
            if expr and type(expr).__name__ == "CapabilityCall":
                results.append(".".join(expr.path))
        elif type(stmt).__name__ == "Assignment":
            val = getattr(stmt, "value", None)
            if val and type(val).__name__ == "CapabilityCall":
                results.append(".".join(val.path))
        # recurse into sub-blocks
        for sub_attr in ("then_block", "else_block", "body"):
            sub = getattr(stmt, sub_attr, None)
            if sub and hasattr(sub, "statements"):
                results.extend(_collect_cap_calls(sub))
    return results


def _explain_via_regex(source: str) -> ProgramExplanation:
    capabilities = re.findall(r"^use\s+([\w.]+)", source, re.MULTILINE)
    actions = re.findall(r"^action\s+(\w+)\s*\(", source, re.MULTILINE)
    agents = re.findall(r"^agent\s+(\w+)\s*:", source, re.MULTILINE)
    mode = _infer_mode_regex(source, capabilities)
    reversible, irreversible = _classify_ops_regex(source, capabilities)
    suggestions = _generate_suggestions(source, mode, capabilities)
    return ProgramExplanation(
        mode=mode,
        capabilities=capabilities,
        actions=actions,
        agents=agents,
        reversible_ops=reversible,
        irreversible_ops=irreversible,
        suggestions=suggestions,
    )


_SAFE_CAPS = {"sensitive.transfer", "sensitive.delete", "sensitive.deploy"}
_FLOW_KEYWORDS = {"agent ", "watch:", "schedule:"}


def _infer_mode_regex(source: str, capabilities: list[str]) -> str:
    if any(kw in source for kw in _FLOW_KEYWORDS):
        return "flow"
    if any(cap in _SAFE_CAPS for cap in capabilities):
        return "safe"
    if "audit: full" in source or "reversible: false" in source:
        return "safe"
    return "fast"


def _classify_ops_regex(
    source: str, capabilities: list[str]
) -> tuple[list[str], list[str]]:
    reversible = []
    irreversible = []
    for cap in capabilities:
        if any(s in cap for s in ("transfer", "delete", "deploy")):
            irreversible.append(cap)
        else:
            reversible.append(cap)
    if "reversible: false" in source:
        actions = re.findall(r"action\s+(\w+).*?reversible:\s*false", source, re.DOTALL)
        for a in actions:
            if f"action {a}" not in irreversible:
                irreversible.append(f"action {a}")
    return reversible, irreversible


def _generate_suggestions(
    source: str, mode: str, capabilities: list[str]
) -> list[str]:
    suggestions = []
    if mode == "safe" and "audit: full" not in source:
        suggestions.append("Considera 'audit: full' en acciones de modo safe")
    if "sensitive" in " ".join(capabilities) and "reversible:" not in source:
        suggestions.append("sensitive.* requiere declarar 'reversible:' explícitamente")
    if "resolve(" in source and "fail_safe()" not in source:
        suggestions.append("Agrega 'unknown: fail_safe()' a bloques resolve")
    return suggestions
