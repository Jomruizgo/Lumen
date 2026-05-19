"""Sistema de audit log append-only en JSON Lines."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class AuditEventType(str, Enum):
    DECISION = "decision"
    EXECUTION = "execution"
    RESOLUTION = "resolution"
    ESCALATION = "escalation"
    UNDO = "undo"
    ERROR = "error"
    UNDO_FAILED = "undo_failed"


class AuditMode(str, Enum):
    FAST = "fast"
    SAFE = "safe"
    FLOW = "flow"


@dataclass
class AuditEvent:
    event: AuditEventType
    mode: AuditMode
    action_id: str = field(default_factory=lambda: str(uuid4()))
    program: str = ""
    program_hash: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    reversible: bool = False
    human_approved: bool = False
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "program": self.program,
            "program_hash": self.program_hash,
            "event": self.event.value,
            "mode": self.mode.value,
            "action_id": self.action_id,
            "details": self.details,
            "confidence": self.confidence,
            "reversible": self.reversible,
            "human_approved": self.human_approved,
        }


def _get_audit_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Lumen" / "audit"
    return Path.home() / ".lumen" / "audit"


class AuditLog:
    """Audit log append-only en JSON Lines. Thread-safe."""

    def __init__(self, audit_dir: Path | None = None) -> None:
        self._dir = audit_dir or _get_audit_dir()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()

    def _log_file(self, date: str | None = None) -> Path:
        if date is None:
            date = datetime.now(UTC).strftime("%Y-%m-%d")
        return self._dir / f"{date}.jsonl"

    async def record(self, event: AuditEvent) -> None:
        async with self._write_lock:
            log_file = self._log_file()
            line = json.dumps(event.to_dict(), ensure_ascii=False) + "\n"
            await asyncio.to_thread(self._append_line, log_file, line)

    def record_sync(self, event: AuditEvent) -> None:
        log_file = self._log_file()
        line = json.dumps(event.to_dict(), ensure_ascii=False) + "\n"
        self._append_line(log_file, line)

    @staticmethod
    def _append_line(path: Path, line: str) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

    async def query(
        self,
        action: str | None = None,
        since: datetime | None = None,
        status: str | None = None,
        mode: AuditMode | None = None,
        reversible: bool | None = None,
    ) -> list[AuditEvent]:
        results: list[AuditEvent] = []

        for log_file in sorted(self._dir.glob("*.jsonl")):
            date_str = log_file.stem
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                continue

            if since and file_date < since.replace(hour=0, minute=0, second=0, microsecond=0):
                continue

            lines = await asyncio.to_thread(self._read_lines, log_file)
            for line in lines:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event = self._dict_to_event(data)
                if event is None:
                    continue

                if action and data.get("details", {}).get("action") != action:
                    if data.get("event") != action:
                        continue
                if since:
                    ts = datetime.fromisoformat(data["ts"])
                    if ts < since:
                        continue
                if mode and data.get("mode") != mode.value:
                    continue
                if reversible is not None and data.get("reversible") != reversible:
                    continue

                results.append(event)

        return results

    @staticmethod
    def _read_lines(path: Path) -> list[str]:
        with open(path, encoding="utf-8") as f:
            return f.readlines()

    @staticmethod
    def _dict_to_event(data: dict[str, Any]) -> AuditEvent | None:
        try:
            return AuditEvent(
                ts=data.get("ts", ""),
                program=data.get("program", ""),
                program_hash=data.get("program_hash", ""),
                event=AuditEventType(data["event"]),
                mode=AuditMode(data["mode"]),
                action_id=data.get("action_id", ""),
                details=data.get("details", {}),
                confidence=float(data.get("confidence", 0.0)),
                reversible=bool(data.get("reversible", False)),
                human_approved=bool(data.get("human_approved", False)),
            )
        except (KeyError, ValueError):
            return None


def compute_program_hash(source: str) -> str:
    return "sha256:" + hashlib.sha256(source.encode()).hexdigest()
