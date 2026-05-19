"""Sistema de undo basado en compensating actions."""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4


def _get_undo_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Lumen" / "undo"
    return Path.home() / ".lumen" / "undo"


@dataclass
class CompensatingAction:
    action_id: str
    compensating_fn: str
    compensating_args: dict[str, Any]
    window_seconds: float
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    dependencies: list[str] = field(default_factory=list)

    def is_within_window(self) -> bool:
        created = datetime.fromisoformat(self.created_at)
        return datetime.now(UTC) < created + timedelta(seconds=self.window_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "compensating_fn": self.compensating_fn,
            "compensating_args": self.compensating_args,
            "window_seconds": self.window_seconds,
            "created_at": self.created_at,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompensatingAction:
        return cls(
            action_id=data["action_id"],
            compensating_fn=data["compensating_fn"],
            compensating_args=data["compensating_args"],
            window_seconds=float(data["window_seconds"]),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            dependencies=data.get("dependencies", []),
        )


@dataclass
class UndoResult:
    success: bool
    action_id: str
    message: str = ""


class UndoOutsideWindowError(Exception):
    """LMN-0060 — Undo fuera de ventana de tiempo."""

    code = "LMN-0060"


class UndoChainBrokenError(Exception):
    """LMN-0070 — Cadena de undo no se pudo completar."""

    code = "LMN-0070"


class UndoManager:
    """Gestión de compensating actions para undo."""

    def __init__(self, undo_dir: Path | None = None) -> None:
        self._dir = undo_dir or _get_undo_dir()
        self._dir.mkdir(parents=True, exist_ok=True)

    def register(
        self,
        action_id: str,
        compensating_fn: str,
        compensating_args: dict[str, Any],
        window_seconds: float,
        dependencies: list[str] | None = None,
    ) -> None:
        comp = CompensatingAction(
            action_id=action_id,
            compensating_fn=compensating_fn,
            compensating_args=compensating_args,
            window_seconds=window_seconds,
            dependencies=dependencies or [],
        )
        path = self._dir / f"{action_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(comp.to_dict(), f, ensure_ascii=False, indent=2)

    def _load(self, action_id: str) -> CompensatingAction | None:
        path = self._dir / f"{action_id}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return CompensatingAction.from_dict(json.load(f))

    def _delete(self, action_id: str) -> None:
        path = self._dir / f"{action_id}.json"
        if path.exists():
            path.unlink()

    def undo(self, action_id: str) -> UndoResult:
        comp = self._load(action_id)
        if comp is None:
            return UndoResult(False, action_id, "Acción no encontrada o ya deshecha")

        if not comp.is_within_window():
            raise UndoOutsideWindowError(
                f"Ventana de undo expirada para {action_id}"
            )

        for dep_id in reversed(comp.dependencies):
            dep_result = self.undo(dep_id)
            if not dep_result.success:
                raise UndoChainBrokenError(
                    f"No se pudo deshacer dependencia {dep_id}: {dep_result.message}"
                )

        try:
            self._execute_compensating(comp)
            self._delete(action_id)
            return UndoResult(True, action_id, "Deshecho exitosamente")
        except Exception as e:
            return UndoResult(False, action_id, f"Compensating action falló: {e}")

    @staticmethod
    def _execute_compensating(comp: CompensatingAction) -> None:
        pass

    def list_reversible(self, since: datetime | None = None) -> list[CompensatingAction]:
        results = []
        for path in self._dir.glob("*.json"):
            with open(path, encoding="utf-8") as f:
                try:
                    comp = CompensatingAction.from_dict(json.load(f))
                except (KeyError, ValueError):
                    continue

            if not comp.is_within_window():
                continue

            if since:
                created = datetime.fromisoformat(comp.created_at)
                if created < since:
                    continue

            results.append(comp)

        return sorted(results, key=lambda c: c.created_at, reverse=True)
