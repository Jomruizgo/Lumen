"""Clase base abstracta para todas las capacidades de Lumen."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ExecutionContext:
    """Contexto de ejecución pasado a cada capability."""

    capabilities: dict[str, Any] = field(default_factory=dict)
    audit_log: Any = None
    undo_manager: Any = None
    escalation_handler: Any = None
    mode: Literal["fast", "safe", "flow"] = "fast"
    dry_run: bool = False
    program_path: str = ""
    program_hash: str = ""


@dataclass
class Result:
    """Resultado de una capability: ok o fail."""

    success: bool
    value: Any = None
    error: str = ""
    action_id: str = ""

    @classmethod
    def ok(cls, value: Any, action_id: str = "") -> Result:
        return cls(success=True, value=value, action_id=action_id)

    @classmethod
    def fail(cls, error: str, action_id: str = "") -> Result:
        return cls(success=False, error=error, action_id=action_id)


@dataclass
class CapabilityDescription:
    """Descripción de una capability para el LLM resolver."""

    name: str
    signature: str
    description: str
    examples: list[str] = field(default_factory=list)
    return_type: str = "any"


class NotReversibleError(Exception):
    """Capacidad no tiene undo."""


class CapabilityNotAuthorized(Exception):
    """LMN-0001 — Capacidad usada sin autorización en sandbox."""

    code = "LMN-0001"


class Capability(ABC):
    """Clase base para todas las capacidades de Lumen."""

    name: str
    mode: Literal["fast", "safe"]
    reversible: bool
    requires_approval: bool

    @abstractmethod
    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        """Ejecuta la capacidad con los argumentos dados."""
        ...

    async def undo(self, action_id: str, context: ExecutionContext) -> Result:
        """Deshace la ejecución si es reversible."""
        if not self.reversible:
            raise NotReversibleError(f"La capacidad {self.name} no es reversible")
        return Result.fail(f"undo no implementado para {self.name}")

    @abstractmethod
    def describe(self) -> CapabilityDescription:
        """Descripción para el resolver LLM."""
        ...


class CapabilityRegistry:
    """Registro global de capacidades disponibles."""

    _registry: dict[str, type[Capability]] = {}

    @classmethod
    def register(cls, capability_class: type[Capability]) -> type[Capability]:
        instance = capability_class.__new__(capability_class)
        cls._registry[instance.name] = capability_class
        return capability_class

    @classmethod
    def get(cls, name: str) -> type[Capability] | None:
        return cls._registry.get(name)

    @classmethod
    def all_names(cls) -> list[str]:
        return sorted(cls._registry.keys())
