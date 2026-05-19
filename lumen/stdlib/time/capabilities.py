"""Capacidades time.*: calendario, eventos, zonas horarias."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from lumen.stdlib.base import (
    Capability,
    CapabilityDescription,
    ExecutionContext,
    Result,
)


def _parse_range(range_str: str) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if range_str == "today":
        return today_start, today_start + timedelta(days=1)
    if range_str == "tomorrow":
        return today_start + timedelta(days=1), today_start + timedelta(days=2)
    if range_str == "this_week":
        return today_start, today_start + timedelta(days=7)
    if range_str == "last_24h":
        return now - timedelta(hours=24), now
    return today_start, today_start + timedelta(days=1)


class TimeNow(Capability):
    name = "time.now"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        tz: str = str(args.get("timezone", "UTC"))
        now = datetime.now(UTC)
        return Result.ok({
            "iso": now.isoformat(),
            "timestamp": now.timestamp(),
            "timezone": tz,
        })

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="time.now(timezone: text = 'UTC') -> time",
            description="Retorna el instante actual con timezone.",
            examples=["time.now()", 'time.now(timezone="America/Mexico_City")'],
        )


class TimeWait(Capability):
    name = "time.wait"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        duration: float = float(args.get("seconds", args.get("duration", 0)))

        if context.dry_run:
            return Result.ok({"waited_seconds": duration, "dry_run": True})

        await asyncio.sleep(duration)
        return Result.ok({"waited_seconds": duration})

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="time.wait(duration: time) -> unit",
            description="Espera el tiempo especificado de forma asíncrona.",
            examples=["time.wait(5min)", "time.wait(30s)"],
        )


class TimeReadCalendar(Capability):
    name = "time.read.calendar"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        range_str: str = str(args.get("range", "today"))

        if context.dry_run:
            start, end = _parse_range(range_str)
            return Result.ok([
                {
                    "id": "mock-event-001",
                    "title": "Mock Event (dry-run)",
                    "start": start.isoformat(),
                    "end": (start + timedelta(hours=1)).isoformat(),
                    "attendees": [],
                }
            ])

        return Result.ok([])

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="read.calendar(range: text) -> List<Event>",
            description="Lee eventos del calendario en el rango especificado.",
            examples=['read.calendar(range="today")', 'read.calendar(range="this_week")'],
        )


class TimeCreateEvent(Capability):
    name = "time.create.event"
    mode = "fast"
    reversible = True
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        title: str = str(args.get("title", ""))
        start: str = str(args.get("start", ""))
        end: str = str(args.get("end", ""))
        attendees: list[str] = args.get("attendees", [])

        if not title or not start:
            return Result.fail("create.event requiere 'title' y 'start'")

        if context.dry_run:
            return Result.ok({
                "title": title,
                "start": start,
                "end": end,
                "attendees": attendees,
                "dry_run": True,
            })

        import uuid
        event_id = str(uuid.uuid4())
        return Result.ok(
            {
                "id": event_id,
                "title": title,
                "start": start,
                "end": end,
                "attendees": attendees,
                "status": "created",
            },
            action_id=event_id,
        )

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="create.event(title: text, start: time, end: time, attendees: List<EmailAddress>) -> Reversible<Event>",
            description="Crea un evento en el calendario. Reversible (se puede cancelar).",
            examples=["create.event(title='Team meeting', start='2026-05-20T10:00', end='2026-05-20T11:00')"],
        )


class TimeFindFreetime(Capability):
    name = "time.find.freetime"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        duration_minutes: int = int(args.get("duration_minutes", 60))
        range_str: str = str(args.get("range", "this_week"))

        start, end = _parse_range(range_str)

        if context.dry_run:
            return Result.ok([
                {
                    "start": (start + timedelta(hours=9)).isoformat(),
                    "end": (start + timedelta(hours=9, minutes=duration_minutes)).isoformat(),
                    "duration_minutes": duration_minutes,
                }
            ])

        slots = []
        current = start.replace(hour=9, minute=0)
        while current < end:
            slot_end = current + timedelta(minutes=duration_minutes)
            if slot_end.hour <= 18:
                slots.append({
                    "start": current.isoformat(),
                    "end": slot_end.isoformat(),
                    "duration_minutes": duration_minutes,
                })
            current += timedelta(hours=1)
            if len(slots) >= 5:
                break

        return Result.ok(slots)

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="find.freetime(duration: time, range: text) -> List<TimeSlot>",
            description="Encuentra slots de tiempo libre en el calendario.",
            examples=["find.freetime(duration=1h, range='this_week')"],
        )
