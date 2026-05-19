"""Tests para el sistema de undo."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lumen.runtime.undo import (
    CompensatingAction,
    UndoChainBrokenError,
    UndoManager,
    UndoOutsideWindowError,
)


@pytest.fixture
def undo_manager(tmp_path: Path) -> UndoManager:
    return UndoManager(undo_dir=tmp_path / "undo")


def test_registers_compensating_action(undo_manager: UndoManager, tmp_path: Path) -> None:
    undo_manager.register(
        action_id="abc-123",
        compensating_fn="transfer.money",
        compensating_args={"from": "B", "to": "A", "amount": "$100 USD"},
        window_seconds=86400,
    )
    path = undo_manager._dir / "abc-123.json"
    assert path.exists()
    comp = undo_manager._load("abc-123")
    assert comp is not None
    assert comp.action_id == "abc-123"
    assert comp.window_seconds == 86400


def test_undo_within_window_succeeds(undo_manager: UndoManager) -> None:
    undo_manager.register(
        action_id="xyz-456",
        compensating_fn="delete_file",
        compensating_args={"path": "/tmp/test.txt"},
        window_seconds=3600,
    )
    result = undo_manager.undo("xyz-456")
    assert result.success
    assert not (undo_manager._dir / "xyz-456.json").exists()


def test_undo_outside_window_fails(undo_manager: UndoManager) -> None:
    past_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    comp = CompensatingAction(
        action_id="expired-001",
        compensating_fn="noop",
        compensating_args={},
        window_seconds=60,
        created_at=past_time,
    )
    import json

    with open(undo_manager._dir / "expired-001.json", "w") as f:
        json.dump(comp.to_dict(), f)

    with pytest.raises(UndoOutsideWindowError):
        undo_manager.undo("expired-001")


def test_undo_nonexistent_returns_failure(undo_manager: UndoManager) -> None:
    result = undo_manager.undo("nonexistent-999")
    assert not result.success
    assert "no encontrada" in result.message.lower()


def test_list_reversible(undo_manager: UndoManager) -> None:
    undo_manager.register("a1", "fn1", {}, 3600)
    undo_manager.register("a2", "fn2", {}, 3600)

    reversible = undo_manager.list_reversible()
    ids = [c.action_id for c in reversible]
    assert "a1" in ids
    assert "a2" in ids


def test_list_reversible_excludes_expired(undo_manager: UndoManager) -> None:
    import json

    undo_manager.register("active", "fn", {}, 3600)

    past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    comp = CompensatingAction(
        action_id="expired", compensating_fn="fn", compensating_args={}, window_seconds=60, created_at=past
    )
    with open(undo_manager._dir / "expired.json", "w") as f:
        json.dump(comp.to_dict(), f)

    reversible = undo_manager.list_reversible()
    ids = [c.action_id for c in reversible]
    assert "active" in ids
    assert "expired" not in ids


def test_undo_chain_executes_in_reverse_order(undo_manager: UndoManager) -> None:
    undo_manager.register("parent", "fn_parent", {}, 3600)
    undo_manager.register("child", "fn_child", {}, 3600, dependencies=["parent"])

    result = undo_manager.undo("child")
    assert result.success
    assert not (undo_manager._dir / "child.json").exists()
    assert not (undo_manager._dir / "parent.json").exists()


def test_compensating_action_is_within_window() -> None:
    comp = CompensatingAction("id", "fn", {}, window_seconds=3600)
    assert comp.is_within_window()


def test_compensating_action_outside_window() -> None:
    past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    comp = CompensatingAction("id", "fn", {}, window_seconds=60, created_at=past)
    assert not comp.is_within_window()
