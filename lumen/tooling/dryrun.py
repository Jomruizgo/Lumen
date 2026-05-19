"""Dry-run mode: muestra plan de ejecución sin ejecutar nada."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ExecutionStep:
    step_num: int
    description: str
    capability: str | None = None
    args: dict[str, str] = field(default_factory=dict)
    requires_approval: bool = False
    reversible: bool | str = True


@dataclass
class DryRunPlan:
    mode: str
    steps: list[ExecutionStep]
    requires_approvals: int = 0
    irreversible_count: int = 0

    def to_text(self) -> str:
        lines = [
            f"[DRY-RUN] Modo: {self.mode.upper()}",
            f"Total de pasos: {len(self.steps)}",
        ]
        if self.requires_approvals:
            lines.append(f"Aprobaciones requeridas: {self.requires_approvals}")
        if self.irreversible_count:
            lines.append(f"Operaciones irreversibles: {self.irreversible_count}")
        lines.append("")
        lines.append("Plan de ejecución:")
        lines.append("-" * 50)

        for step in self.steps:
            prefix = f"  [{step.step_num}]"
            if step.requires_approval:
                prefix += " [APROBACION]"
            if step.reversible is False:
                prefix += " [IRREVERSIBLE]"
            lines.append(f"{prefix} {step.description}")

        lines.append("-" * 50)
        lines.append("[No se ejecutó nada. Use 'lumen run <file>' para ejecutar.]")
        return "\n".join(lines)


def dry_run(source: str) -> DryRunPlan:
    """Analiza un programa Lumen y retorna plan de ejecución sin ejecutar.

    Usa compilador real cuando disponible; regex como fallback.
    """
    try:
        return _dry_run_via_compiler(source)
    except Exception:
        return _dry_run_via_regex(source)


def _dry_run_via_compiler(source: str) -> DryRunPlan:
    from lumen.compiler.pipeline import compile_source

    result = compile_source(source)
    if not result.ok or result.program is None:
        raise RuntimeError("Compilation failed")

    program = result.program.instrumented.resolved.typed.ast
    mode = result.program.mode
    steps: list[ExecutionStep] = []
    step_num = 0

    IRREVERSIBLE = frozenset({"sensitive.transfer", "sensitive.delete", "sensitive.deploy"})
    NEEDS_APPROVAL = frozenset({"sensitive.transfer", "sensitive.delete", "sensitive.deploy"})

    # declared capabilities
    cap_names = [cap.path_str for cap in program.capabilities]
    if cap_names:
        step_num += 1
        steps.append(ExecutionStep(
            step_num=step_num,
            description=f"Declarar capacidades: {', '.join(cap_names)}",
        ))

    # walk top-level statements
    for tl in program.top_levels:
        tl_type = type(tl).__name__
        if tl_type == "ActionDecl":
            step_num += 1
            steps.append(ExecutionStep(
                step_num=step_num,
                description=f"Definir action: {tl.name}({', '.join(p.name for p in tl.params)})",
            ))
            if tl.body.execute:
                for cap_path in _collect_cap_calls_flat(tl.body.execute.body):
                    step_num += 1
                    needs_appr = any(cap_path.startswith(p) for p in NEEDS_APPROVAL)
                    is_irrev = any(cap_path.startswith(p) for p in IRREVERSIBLE)
                    rev: bool | str = False if is_irrev else True
                    if tl.body.reversible and not is_irrev:
                        rev_val = tl.body.reversible.value
                        rev = str(rev_val) if not isinstance(rev_val, bool) else rev_val
                    steps.append(ExecutionStep(
                        step_num=step_num,
                        description=f"  → {cap_path}()",
                        capability=cap_path,
                        requires_approval=needs_appr,
                        reversible=rev,
                    ))

        elif tl_type == "AgentDecl":
            step_num += 1
            steps.append(ExecutionStep(
                step_num=step_num,
                description=f"Iniciar agent: {tl.name} (persistente)",
            ))

        elif tl_type == "FunctionDecl":
            step_num += 1
            steps.append(ExecutionStep(
                step_num=step_num,
                description=f"Definir función: {tl.name}",
            ))

        elif tl_type in ("ExpressionStatement", "Assignment"):
            step_num += 1
            steps.append(ExecutionStep(
                step_num=step_num,
                description=f"Ejecutar: {type(tl).__name__}",
            ))

    approvals = sum(1 for s in steps if s.requires_approval)
    irreversibles = sum(1 for s in steps if s.reversible is False)
    return DryRunPlan(mode=mode, steps=steps, requires_approvals=approvals, irreversible_count=irreversibles)


def _collect_cap_calls_flat(block: object) -> list[str]:
    """Collect CapabilityCall paths from a Block (non-recursive for brevity)."""
    results: list[str] = []
    statements = getattr(block, "statements", [])
    for stmt in statements:
        t = type(stmt).__name__
        if t == "CapabilityCall":
            results.append(".".join(stmt.path))
        elif t == "ExpressionStatement":
            expr = getattr(stmt, "expression", None)
            if expr and type(expr).__name__ == "CapabilityCall":
                results.append(".".join(expr.path))
        elif t == "Assignment":
            val = getattr(stmt, "value", None)
            if val and type(val).__name__ == "CapabilityCall":
                results.append(".".join(val.path))
        # recurse one level
        for sub_attr in ("then_block", "else_block", "body"):
            sub = getattr(stmt, sub_attr, None)
            if sub and hasattr(sub, "statements"):
                results.extend(_collect_cap_calls_flat(sub))
    return results


def _dry_run_via_regex(source: str) -> DryRunPlan:
    mode = _infer_mode(source)
    steps = _extract_steps(source)
    approvals = sum(1 for s in steps if s.requires_approval)
    irreversibles = sum(1 for s in steps if s.reversible is False)
    return DryRunPlan(mode=mode, steps=steps, requires_approvals=approvals, irreversible_count=irreversibles)


def _infer_mode(source: str) -> str:
    if re.search(r"^agent\s+\w+", source, re.MULTILINE):
        return "flow"
    if re.search(r"use\s+sensitive\.", source):
        return "safe"
    if "audit: full" in source or "reversible: false" in source:
        return "safe"
    return "fast"


_SENSITIVE_CAPS = {"transfer.money", "delete.permanent", "deploy.production"}


def _extract_steps(source: str) -> list[ExecutionStep]:
    steps: list[ExecutionStep] = []
    step_num = 0

    cap_uses = re.findall(r"use\s+([\w.]+)", source, re.MULTILINE)
    if cap_uses:
        step_num += 1
        steps.append(ExecutionStep(
            step_num=step_num,
            description=f"Declarar capacidades: {', '.join(cap_uses)}",
        ))

    fn_calls = re.findall(r"(\w+\.?\w*)\s*\(", source)
    seen: set[str] = set()
    for call in fn_calls:
        if call in seen or call in {"filter", "if", "for", "match", "return", "resolve"}:
            continue
        seen.add(call)
        is_sensitive = any(s in call for s in ["transfer", "delete", "deploy"])
        step_num += 1
        steps.append(ExecutionStep(
            step_num=step_num,
            description=f"Llamar {call}()",
            capability=call,
            requires_approval=is_sensitive,
            reversible=False if "delete" in call or "deploy" in call else True,
        ))

    action_defs = re.findall(r"^action\s+(\w+)", source, re.MULTILINE)
    for action in action_defs:
        step_num += 1
        steps.append(ExecutionStep(
            step_num=step_num,
            description=f"Definir action: {action}",
        ))

    return steps
