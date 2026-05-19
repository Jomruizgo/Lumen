"""Tests para capabilities sensitive.*."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from lumen.runtime.escalation import ApprovalResponse, EscalationRequest
from lumen.stdlib.base import ExecutionContext
from lumen.stdlib.sensitive.capabilities import (
    SensitiveDeletePermanent,
    SensitiveDeployProduction,
    SensitiveTransferMoney,
)


@pytest.fixture
def dry_ctx() -> ExecutionContext:
    return ExecutionContext(mode="safe", dry_run=True)


@pytest.fixture
def ctx_with_approval() -> ExecutionContext:
    mock_handler = AsyncMock()
    mock_handler.request_approval = AsyncMock(
        return_value=ApprovalResponse(approved=True)
    )
    return ExecutionContext(mode="safe", escalation_handler=mock_handler)


@pytest.fixture
def ctx_with_rejection() -> ExecutionContext:
    mock_handler = AsyncMock()
    mock_handler.request_approval = AsyncMock(
        return_value=ApprovalResponse(approved=False, reason="Rechazado en test")
    )
    return ExecutionContext(mode="safe", escalation_handler=mock_handler)


@pytest.mark.asyncio
async def test_transfer_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = SensitiveTransferMoney()
    result = await cap.execute(
        {"from": "account_A", "to": "account_B", "amount": "$1000 USD"},
        dry_ctx,
    )
    assert result.success
    assert "dry-run" in result.value["status"]


@pytest.mark.asyncio
async def test_transfer_approved(ctx_with_approval: ExecutionContext) -> None:
    cap = SensitiveTransferMoney()
    result = await cap.execute(
        {"from": "account_A", "to": "account_B", "amount": "$500 USD"},
        ctx_with_approval,
    )
    assert result.success
    assert result.value["status"] == "completed"


@pytest.mark.asyncio
async def test_transfer_rejected(ctx_with_rejection: ExecutionContext) -> None:
    cap = SensitiveTransferMoney()
    result = await cap.execute(
        {"from": "account_A", "to": "account_B", "amount": "$500 USD"},
        ctx_with_rejection,
    )
    assert not result.success
    assert "rechazado" in result.error.lower() or "Rechazado" in result.error


@pytest.mark.asyncio
async def test_transfer_missing_args(dry_ctx: ExecutionContext) -> None:
    cap = SensitiveTransferMoney()
    result = await cap.execute({"from": "A"}, dry_ctx)
    assert not result.success


@pytest.mark.asyncio
async def test_delete_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = SensitiveDeletePermanent()
    result = await cap.execute({"path": "/tmp/test"}, dry_ctx)
    assert result.success
    assert "dry-run" in result.value["status"]


@pytest.mark.asyncio
async def test_delete_approved(tmp_path: Path, ctx_with_approval: ExecutionContext) -> None:
    test_file = tmp_path / "to_delete.txt"
    test_file.write_text("delete me", encoding="utf-8")

    cap = SensitiveDeletePermanent()
    result = await cap.execute({"path": str(test_file)}, ctx_with_approval)
    assert result.success
    assert not test_file.exists()


@pytest.mark.asyncio
async def test_delete_not_found(ctx_with_approval: ExecutionContext) -> None:
    cap = SensitiveDeletePermanent()
    result = await cap.execute({"path": "/nonexistent/path/xyz"}, ctx_with_approval)
    assert not result.success


@pytest.mark.asyncio
async def test_deploy_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = SensitiveDeployProduction()
    result = await cap.execute(
        {"system": "api-service", "version": "v2.1.0"}, dry_ctx
    )
    assert result.success
    assert "dry-run" in result.value["status"]


@pytest.mark.asyncio
async def test_deploy_missing_args(dry_ctx: ExecutionContext) -> None:
    cap = SensitiveDeployProduction()
    result = await cap.execute({"system": "api-service"}, dry_ctx)
    assert not result.success


def test_transfer_describe() -> None:
    cap = SensitiveTransferMoney()
    desc = cap.describe()
    assert "transfer" in desc.name.lower()
    assert "approval" in desc.description.lower() or "aprobación" in desc.description.lower()
