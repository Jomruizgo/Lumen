"""Tests para la clase base de capabilities."""

from __future__ import annotations

from typing import Any

import pytest

from lumen.stdlib.base import (
    Capability,
    CapabilityDescription,
    CapabilityRegistry,
    ExecutionContext,
    NotReversibleError,
    Result,
)


class MockCapability(Capability):
    name = "mock.test"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        return Result.ok({"args": args})

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="mock.test() -> any",
            description="Mock para tests",
        )


class ReversibleMock(Capability):
    name = "mock.reversible"
    mode = "fast"
    reversible = True
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        return Result.ok("executed", action_id="test-123")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(name=self.name, signature="mock()", description="")


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext(mode="fast")


@pytest.mark.asyncio
async def test_capability_execute(context: ExecutionContext) -> None:
    cap = MockCapability()
    result = await cap.execute({"key": "value"}, context)
    assert result.success
    assert result.value == {"args": {"key": "value"}}


@pytest.mark.asyncio
async def test_capability_undo_not_reversible(context: ExecutionContext) -> None:
    cap = MockCapability()
    with pytest.raises(NotReversibleError):
        await cap.undo("action-001", context)


@pytest.mark.asyncio
async def test_capability_undo_reversible(context: ExecutionContext) -> None:
    cap = ReversibleMock()
    result = await cap.undo("test-123", context)
    assert not result.success
    assert "no implementado" in result.error.lower()


def test_result_ok() -> None:
    r = Result.ok("hello", action_id="abc")
    assert r.success
    assert r.value == "hello"
    assert r.action_id == "abc"


def test_result_fail() -> None:
    r = Result.fail("error message")
    assert not r.success
    assert r.error == "error message"
    assert r.value is None


def test_capability_describe() -> None:
    cap = MockCapability()
    desc = cap.describe()
    assert desc.name == "mock.test"
    assert "mock" in desc.signature.lower() or desc.signature != ""


def test_execution_context_defaults() -> None:
    ctx = ExecutionContext()
    assert ctx.mode == "fast"
    assert ctx.dry_run is False
    assert ctx.capabilities == {}


def test_execution_context_dry_run() -> None:
    ctx = ExecutionContext(dry_run=True)
    assert ctx.dry_run is True
