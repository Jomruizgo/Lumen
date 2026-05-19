"""Tests para el sistema de audit log."""

from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lumen.runtime.audit import AuditEvent, AuditEventType, AuditLog, AuditMode, compute_program_hash


@pytest.fixture
def tmp_audit_dir(tmp_path: Path) -> Path:
    return tmp_path / "audit"


@pytest.fixture
def audit_log(tmp_audit_dir: Path) -> AuditLog:
    return AuditLog(audit_dir=tmp_audit_dir)


def make_event(**kwargs: object) -> AuditEvent:
    defaults = {
        "event": AuditEventType.EXECUTION,
        "mode": AuditMode.FAST,
        "program": "test.lumen",
    }
    defaults.update(kwargs)
    return AuditEvent(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_records_event(audit_log: AuditLog) -> None:
    event = make_event()
    await audit_log.record(event)

    log_file = audit_log._log_file()
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["event"] == "execution"


@pytest.mark.asyncio
async def test_appends_does_not_overwrite(audit_log: AuditLog) -> None:
    await audit_log.record(make_event(action_id="first"))
    await audit_log.record(make_event(action_id="second"))

    log_file = audit_log._log_file()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    ids = [json.loads(line)["action_id"] for line in lines]
    assert "first" in ids
    assert "second" in ids


@pytest.mark.asyncio
async def test_queries_by_action(audit_log: AuditLog) -> None:
    await audit_log.record(make_event(
        event=AuditEventType.EXECUTION,
        details={"action": "transfer.money"}
    ))
    await audit_log.record(make_event(
        event=AuditEventType.EXECUTION,
        details={"action": "send.email"}
    ))

    results = await audit_log.query(action="transfer.money")
    assert len(results) == 1
    assert results[0].details["action"] == "transfer.money"


@pytest.mark.asyncio
async def test_queries_by_time_range(audit_log: AuditLog) -> None:
    # Use explicit timestamps so the test is deterministic (no wall-clock races)
    from datetime import timezone
    old_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
    new_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    since = datetime(2022, 1, 1, tzinfo=timezone.utc)

    old_event = make_event(action_id="old")
    old_event.ts = old_time.isoformat()
    await audit_log.record(old_event)

    new_event = make_event(action_id="new")
    new_event.ts = new_time.isoformat()
    await audit_log.record(new_event)

    results = await audit_log.query(since=since)
    ids = [e.action_id for e in results]
    assert "new" in ids
    assert "old" not in ids


@pytest.mark.asyncio
async def test_queries_by_mode(audit_log: AuditLog) -> None:
    await audit_log.record(make_event(mode=AuditMode.FAST))
    await audit_log.record(make_event(mode=AuditMode.SAFE))

    results = await audit_log.query(mode=AuditMode.SAFE)
    assert all(e.mode == AuditMode.SAFE for e in results)


@pytest.mark.asyncio
async def test_queries_reversible(audit_log: AuditLog) -> None:
    await audit_log.record(make_event(reversible=True))
    await audit_log.record(make_event(reversible=False))

    results = await audit_log.query(reversible=True)
    assert all(e.reversible for e in results)


@pytest.mark.asyncio
async def test_thread_safe_concurrent_writes(audit_log: AuditLog) -> None:
    tasks = [audit_log.record(make_event(action_id=f"event-{i}")) for i in range(20)]
    await asyncio.gather(*tasks)

    log_file = audit_log._log_file()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 20
    for line in lines:
        json.loads(line)


@pytest.mark.asyncio
async def test_works_on_windows_paths(tmp_path: Path) -> None:
    deep_path = tmp_path / "Lumen" / "audit" / "subdir"
    log = AuditLog(audit_dir=deep_path)
    event = make_event()
    await log.record(event)
    assert (deep_path / log._log_file().name).exists()


def test_compute_program_hash() -> None:
    h = compute_program_hash('@lumen 1.0\nprint "Hello"')
    assert h.startswith("sha256:")
    assert len(h) == 7 + 64


def test_event_to_dict_roundtrip() -> None:
    event = make_event(
        event=AuditEventType.DECISION,
        mode=AuditMode.SAFE,
        reversible=True,
        human_approved=True,
        confidence=0.95,
        details={"key": "value"},
    )
    d = event.to_dict()
    assert d["event"] == "decision"
    assert d["mode"] == "safe"
    assert d["reversible"] is True
    assert d["confidence"] == pytest.approx(0.95)
