"""Tests para capabilities time.*."""

from __future__ import annotations

import pytest

from lumen.stdlib.base import ExecutionContext
from lumen.stdlib.time.capabilities import (
    TimeCreateEvent,
    TimeFindFreetime,
    TimeNow,
    TimeReadCalendar,
    TimeWait,
)


@pytest.fixture
def ctx() -> ExecutionContext:
    return ExecutionContext(mode="fast")


@pytest.fixture
def dry_ctx() -> ExecutionContext:
    return ExecutionContext(mode="fast", dry_run=True)


@pytest.mark.asyncio
async def test_time_now(ctx: ExecutionContext) -> None:
    cap = TimeNow()
    result = await cap.execute({}, ctx)
    assert result.success
    assert "iso" in result.value
    assert "T" in result.value["iso"]


@pytest.mark.asyncio
async def test_time_now_has_timestamp(ctx: ExecutionContext) -> None:
    cap = TimeNow()
    result = await cap.execute({}, ctx)
    assert result.success
    assert isinstance(result.value["timestamp"], float)
    assert result.value["timestamp"] > 0


@pytest.mark.asyncio
async def test_time_wait_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = TimeWait()
    result = await cap.execute({"seconds": 100}, dry_ctx)
    assert result.success
    assert result.value["dry_run"] is True


@pytest.mark.asyncio
async def test_time_wait_short(ctx: ExecutionContext) -> None:
    import time

    cap = TimeWait()
    start = time.monotonic()
    result = await cap.execute({"seconds": 0.05}, ctx)
    elapsed = time.monotonic() - start
    assert result.success
    assert elapsed >= 0.04


@pytest.mark.asyncio
async def test_read_calendar_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = TimeReadCalendar()
    result = await cap.execute({"range": "today"}, dry_ctx)
    assert result.success
    assert isinstance(result.value, list)
    assert len(result.value) > 0


@pytest.mark.asyncio
async def test_read_calendar_no_credentials(ctx: ExecutionContext) -> None:
    cap = TimeReadCalendar()
    result = await cap.execute({"range": "today"}, ctx)
    assert result.success
    assert isinstance(result.value, list)


@pytest.mark.asyncio
async def test_create_event_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = TimeCreateEvent()
    result = await cap.execute(
        {
            "title": "Reunión de equipo",
            "start": "2026-05-20T10:00:00Z",
            "end": "2026-05-20T11:00:00Z",
        },
        dry_ctx,
    )
    assert result.success
    assert result.value["dry_run"] is True


@pytest.mark.asyncio
async def test_create_event_missing_title(dry_ctx: ExecutionContext) -> None:
    cap = TimeCreateEvent()
    result = await cap.execute({"start": "2026-05-20T10:00:00Z"}, dry_ctx)
    assert not result.success


@pytest.mark.asyncio
async def test_find_freetime_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = TimeFindFreetime()
    result = await cap.execute({"duration_minutes": 60, "range": "this_week"}, dry_ctx)
    assert result.success
    assert isinstance(result.value, list)
    assert len(result.value) > 0


@pytest.mark.asyncio
async def test_find_freetime_real(ctx: ExecutionContext) -> None:
    cap = TimeFindFreetime()
    result = await cap.execute({"duration_minutes": 30, "range": "this_week"}, ctx)
    assert result.success
    for slot in result.value:
        assert "start" in slot
        assert "end" in slot


def test_time_now_describe() -> None:
    cap = TimeNow()
    desc = cap.describe()
    assert "time.now" in desc.name


def test_read_calendar_describe() -> None:
    cap = TimeReadCalendar()
    desc = cap.describe()
    assert "calendar" in desc.name.lower()
