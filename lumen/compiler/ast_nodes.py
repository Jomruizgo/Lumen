"""Nodos del AST de Lumen.

Todos son pydantic.BaseModel con frozen=True.
Cada nodo tiene `position: SourcePosition` y `pretty_print()`.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict


class SourcePosition(BaseModel):
    model_config = ConfigDict(frozen=True)

    line: int
    col: int
    file: str = ""

    def __str__(self) -> str:
        if self.file:
            return f"{self.file}:{self.line}:{self.col}"
        return f"{self.line}:{self.col}"


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

class LumenTypeNode(BaseModel):
    """Base para nodos de tipo en el AST."""
    model_config = ConfigDict(frozen=True)
    position: SourcePosition

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + repr(self)


class PrimitiveType(LumenTypeNode):
    name: Literal["text", "number", "time", "boolean", "any"]

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + self.name


class ParametrizedType(LumenTypeNode):
    base: str
    args: tuple[LumenTypeNode, ...]

    def pretty_print(self, indent: int = 0) -> str:
        args_str = ", ".join(a.pretty_print() for a in self.args)
        return " " * indent + f"{self.base}<{args_str}>"


class UnionType(LumenTypeNode):
    left: LumenTypeNode
    right: LumenTypeNode

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"{self.left.pretty_print()} | {self.right.pretty_print()}"


Type = Union[PrimitiveType, ParametrizedType, UnionType]


# ---------------------------------------------------------------------------
# Expresiones
# ---------------------------------------------------------------------------

class Expression(BaseModel):
    """Base para todos los nodos de expresión."""
    model_config = ConfigDict(frozen=True)
    position: SourcePosition

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + repr(self)


class Identifier(Expression):
    name: str

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + self.name


class NumberLiteral(Expression):
    value: str  # guardamos como string para preservar el formato

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + self.value


class StringLiteral(Expression):
    value: str

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f'"{self.value}"'


class BooleanLiteral(Expression):
    value: bool

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + ("true" if self.value else "false")


class TimeLiteral(Expression):
    value: str  # e.g., "5min", "2h"

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + self.value


class MoneyLiteral(Expression):
    value: str  # e.g., "$100 USD"
    amount: str
    currency: str  # "USD", "EUR", etc.

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + self.value


class StringInterpolation(Expression):
    parts: tuple[Union[str, Expression], ...]  # str para texto literal, Expression para expresiones

    def pretty_print(self, indent: int = 0) -> str:
        parts_str = ""
        for part in self.parts:
            if isinstance(part, str):
                parts_str += part
            else:
                parts_str += "${" + part.pretty_print() + "}"
        return " " * indent + f'"{parts_str}"'


class BinaryOp(Expression):
    op: str
    left: Expression
    right: Expression

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"({self.left.pretty_print()} {self.op} {self.right.pretty_print()})"


class FunctionCall(Expression):
    name: str
    args: tuple[Expression, ...]
    kwargs: tuple[tuple[str, Expression], ...]

    def pretty_print(self, indent: int = 0) -> str:
        args_str = ", ".join(a.pretty_print() for a in self.args)
        kwargs_str = ", ".join(f"{k}={v.pretty_print()}" for k, v in self.kwargs)
        all_args = ", ".join(filter(None, [args_str, kwargs_str]))
        return " " * indent + f"{self.name}({all_args})"


class CapabilityCall(Expression):
    """Llamada a una capacidad: comm.email(...)"""
    path: tuple[str, ...]  # e.g., ("comm", "email")
    args: tuple[Expression, ...]
    kwargs: tuple[tuple[str, Expression], ...]

    def pretty_print(self, indent: int = 0) -> str:
        path_str = ".".join(self.path)
        args_str = ", ".join(a.pretty_print() for a in self.args)
        kwargs_str = ", ".join(f"{k}={v.pretty_print()}" for k, v in self.kwargs)
        all_args = ", ".join(filter(None, [args_str, kwargs_str]))
        return " " * indent + f"{path_str}({all_args})"


class DotAccess(Expression):
    """Acceso a campo: obj.field"""
    obj: Expression
    field: str

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"{self.obj.pretty_print()}.{self.field}"


class IndexAccess(Expression):
    """Acceso por índice: obj[idx]"""
    obj: Expression
    index: Expression

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"{self.obj.pretty_print()}[{self.index.pretty_print()}]"


class UnaryOp(Expression):
    op: str
    operand: Expression

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"({self.op}{self.operand.pretty_print()})"




# ---------------------------------------------------------------------------
# Anotaciones
# ---------------------------------------------------------------------------

class BecauseAnnotation(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    reason: str

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f'because "{self.reason}"'


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

class Param(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    name: str
    type_annotation: Optional[Type] = None
    default: Optional[Expression] = None

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + self.name
        if self.type_annotation:
            s += f": {self.type_annotation.pretty_print()}"
        if self.default:
            s += f" = {self.default.pretty_print()}"
        return s


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------

class Statement(BaseModel):
    """Base para todos los statements."""
    model_config = ConfigDict(frozen=True)
    position: SourcePosition

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + repr(self)


class Pipeline(Expression):
    """Pipeline de expresiones: a | b | c.

    Es Expression para permitir su uso en assignments y como valor.
    Cuando aparece como top-level statement se envuelve en ExpressionStatement.
    """
    steps: tuple[Expression, ...]

    def pretty_print(self, indent: int = 0) -> str:
        steps_str = " | ".join(s.pretty_print() for s in self.steps)
        return " " * indent + steps_str


class Assignment(Statement):
    target: str
    value: Union[Expression, Any]  # Any permite ResolveBlock (Statement) como RHS
    because: Optional[BecauseAnnotation] = None

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + f"{self.target} = {self.value.pretty_print()}"
        if self.because:
            s += f" {self.because.pretty_print()}"
        return s


class ExpressionStatement(Statement):
    """Un statement que es solo una expresión."""
    expression: Expression

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + self.expression.pretty_print()


class ReturnStatement(Statement):
    value: Optional[Expression] = None

    def pretty_print(self, indent: int = 0) -> str:
        if self.value:
            return " " * indent + f"return {self.value.pretty_print()}"
        return " " * indent + "return"


class PassStatement(Statement):
    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + "pass"


class IfStatement(Statement):
    condition: Expression
    then_block: "Block"
    else_block: Optional["Block"] = None

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + f"if {self.condition.pretty_print()}:\n"
        s += self.then_block.pretty_print(indent + 2)
        if self.else_block:
            s += "\n" + " " * indent + "else:\n"
            s += self.else_block.pretty_print(indent + 2)
        return s


class MatchArm(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    pattern: Expression
    body: Union["Block", Expression]

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"{self.pattern.pretty_print()} -> {self.body.pretty_print()}"


class MatchStatement(Statement):
    subject: Expression
    arms: tuple[MatchArm, ...]

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + f"match {self.subject.pretty_print()}:\n"
        for arm in self.arms:
            s += arm.pretty_print(indent + 2) + "\n"
        return s


class ForStatement(Statement):
    target: str
    iterable: Expression
    body: "Block"

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + f"for {self.target} in {self.iterable.pretty_print()}:\n"
        s += self.body.pretty_print(indent + 2)
        return s


class StrategyClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    name: str  # high_confidence, ambiguous, unknown, ask_user, etc.
    body: Union["Block", Expression]

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"{self.name}: {self.body.pretty_print()}"


class ResolveBlock(Statement):
    subject: Expression
    strategies: tuple[StrategyClause, ...]

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + f"resolve({self.subject.pretty_print()}) {{\n"
        for strategy in self.strategies:
            s += strategy.pretty_print(indent + 2) + "\n"
        s += " " * indent + "}"
        return s


class PrintStatement(Statement):
    value: Expression

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"print {self.value.pretty_print()}"


class UndoStatement(Statement):
    action_id: Expression

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"undo(action_id={self.action_id.pretty_print()})"


# ---------------------------------------------------------------------------
# Bloques
# ---------------------------------------------------------------------------

class Block(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    statements: tuple[Statement, ...]

    def pretty_print(self, indent: int = 0) -> str:
        return "\n".join(s.pretty_print(indent) for s in self.statements)


# ---------------------------------------------------------------------------
# Cláusulas de action/agent
# ---------------------------------------------------------------------------

class RequiresClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    condition: Expression

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"requires: {self.condition.pretty_print()}"


class ExecuteClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    body: Block

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + "execute:\n"
        s += self.body.pretty_print(indent + 2)
        return s


class ReversibleClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    value: Union[bool, str, Expression]  # true, false, "24h", conditional(expr)

    def pretty_print(self, indent: int = 0) -> str:
        if isinstance(self.value, bool):
            val_str = "true" if self.value else "false"
        elif isinstance(self.value, str):
            val_str = self.value
        else:
            val_str = self.value.pretty_print()
        return " " * indent + f"reversible: {val_str}"


class AuditClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    level: Literal["full", "minimal", "silent"]

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"audit: {self.level}"


class ModeClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    mode: Literal["fast", "safe", "flow"]

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"mode: {self.mode}"


class EscalationClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    target: Expression  # webhook(...) or cli

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"escalation: {self.target.pretty_print()}"


# ---------------------------------------------------------------------------
# Cláusulas de agent
# ---------------------------------------------------------------------------

class WatchClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    expression: Expression

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"watch: {self.expression.pretty_print()}"


class OnClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    pattern: Expression
    condition: Optional[Expression] = None  # "where" clause
    body: Block

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + f"on {self.pattern.pretty_print()}"
        if self.condition:
            s += f" where {self.condition.pretty_print()}"
        s += ":\n" + self.body.pretty_print(indent + 2)
        return s


class ScheduleClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    expression: Expression  # cron string o time literal

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"schedule: {self.expression.pretty_print()}"


class ConfigClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    settings: tuple[tuple[str, Expression], ...]

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + "config:\n"
        for key, val in self.settings:
            s += " " * (indent + 2) + f"{key}: {val.pretty_print()}\n"
        return s


class StateClause(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    fields: tuple[tuple[str, Optional[Type], Optional[Expression]], ...]

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + "state:\n"
        for name, typ, default in self.fields:
            line = " " * (indent + 2) + name
            if typ:
                line += f": {typ.pretty_print()}"
            if default:
                line += f" = {default.pretty_print()}"
            s += line + "\n"
        return s


# ---------------------------------------------------------------------------
# Declaraciones top-level
# ---------------------------------------------------------------------------

class VersionDecl(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    major: int
    minor: int

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"@lumen {self.major}.{self.minor}"


class CapabilityDecl(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    path: tuple[str, ...]  # e.g., ("comm", "email")
    alias: Optional[str] = None

    @property
    def path_str(self) -> str:
        return ".".join(self.path)

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + f"use {self.path_str}"
        if self.alias:
            s += f" as {self.alias}"
        return s


class ImportDecl(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    path: str
    alias: Optional[str] = None
    from_std: bool = False

    def pretty_print(self, indent: int = 0) -> str:
        if self.from_std:
            s = " " * indent + f"import {self.path} from std"
        else:
            s = " " * indent + f'import "{self.path}"'
        if self.alias:
            s += f" as {self.alias}"
        return s


class FunctionDecl(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    name: str
    params: tuple[Param, ...]
    return_type: Optional[Type] = None
    body: Block
    doc_comment: Optional[str] = None

    def pretty_print(self, indent: int = 0) -> str:
        params_str = ", ".join(p.pretty_print() for p in self.params)
        s = " " * indent + f"fn {self.name}({params_str})"
        if self.return_type:
            s += f" -> {self.return_type.pretty_print()}"
        s += ":\n" + self.body.pretty_print(indent + 2)
        return s


class ActionBody(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    mode: Optional[ModeClause] = None
    requires: Optional[RequiresClause] = None
    reversible: Optional[ReversibleClause] = None
    audit: Optional[AuditClause] = None
    escalation: Optional[EscalationClause] = None
    execute: Optional[ExecuteClause] = None

    def pretty_print(self, indent: int = 0) -> str:
        parts = []
        for clause in [self.mode, self.requires, self.reversible, self.audit, self.escalation, self.execute]:
            if clause:
                parts.append(clause.pretty_print(indent))
        return "\n".join(parts)


class ActionDecl(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    name: str
    params: tuple[Param, ...]
    body: ActionBody
    doc_comment: Optional[str] = None

    def pretty_print(self, indent: int = 0) -> str:
        params_str = ", ".join(p.pretty_print() for p in self.params)
        s = " " * indent + f"action {self.name}({params_str}):\n"
        s += self.body.pretty_print(indent + 2)
        return s


class AgentBody(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    watch: Optional[WatchClause] = None
    state: Optional[StateClause] = None
    on_clauses: tuple[OnClause, ...]
    schedule: Optional[ScheduleClause] = None
    config: Optional[ConfigClause] = None

    def pretty_print(self, indent: int = 0) -> str:
        parts = []
        for clause in [self.watch, self.state, *self.on_clauses, self.schedule, self.config]:
            if clause:
                parts.append(clause.pretty_print(indent))
        return "\n".join(parts)


class AgentDecl(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    name: str
    body: AgentBody
    doc_comment: Optional[str] = None

    def pretty_print(self, indent: int = 0) -> str:
        s = " " * indent + f"agent {self.name}:\n"
        s += self.body.pretty_print(indent + 2)
        return s


# ---------------------------------------------------------------------------
# Nodo para AuditInjector
# ---------------------------------------------------------------------------

class AuditLogCall(Statement):
    """Nodo inyectado por AuditInjector para registrar audit logs."""
    action_name: str
    level: Literal["full", "minimal", "silent"]
    event_type: Literal["decision", "execution", "result"]
    payload: Optional[Expression] = None

    def pretty_print(self, indent: int = 0) -> str:
        return " " * indent + f"__audit_log__({self.action_name!r}, {self.level!r}, {self.event_type!r})"


# ---------------------------------------------------------------------------
# Tipos de expresion literal (alias)
# ---------------------------------------------------------------------------

LiteralExpr = Union[NumberLiteral, StringLiteral, BooleanLiteral, TimeLiteral, MoneyLiteral]

# ---------------------------------------------------------------------------
# Programa completo
# ---------------------------------------------------------------------------

TopLevel = Union[
    CapabilityDecl,
    AgentDecl,
    ActionDecl,
    FunctionDecl,
    ImportDecl,
    Statement,
]


class Program(BaseModel):
    model_config = ConfigDict(frozen=True)
    position: SourcePosition
    version: VersionDecl
    top_levels: tuple[TopLevel, ...]

    def pretty_print(self, indent: int = 0) -> str:
        parts = [self.version.pretty_print(indent)]
        for tl in self.top_levels:
            parts.append(tl.pretty_print(indent))
        return "\n\n".join(parts)

    @property
    def capabilities(self) -> list[CapabilityDecl]:
        return [tl for tl in self.top_levels if isinstance(tl, CapabilityDecl)]

    @property
    def agents(self) -> list[AgentDecl]:
        return [tl for tl in self.top_levels if isinstance(tl, AgentDecl)]

    @property
    def actions(self) -> list[ActionDecl]:
        return [tl for tl in self.top_levels if isinstance(tl, ActionDecl)]

    @property
    def functions(self) -> list[FunctionDecl]:
        return [tl for tl in self.top_levels if isinstance(tl, FunctionDecl)]
