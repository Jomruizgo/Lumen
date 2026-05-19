"""Tests para los escalation handlers."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from lumen.runtime.escalation import (
    ApprovalResponse,
    CLIEscalation,
    EscalationRequest,
    EscalationTimeout,
)


@pytest.fixture
def request_payload() -> EscalationRequest:
    return EscalationRequest(
        approval_id="test-001",
        action={"name": "transfer.money", "amount": "$1000 USD", "to": "Pedro García"},
        context={"description": "Pago de factura #4521"},
        timeout_seconds=5,
    )


@pytest.mark.asyncio
async def test_cli_approval_with_simulated_input(request_payload: EscalationRequest) -> None:
    handler = CLIEscalation(timeout_seconds=10)

    with patch("builtins.input", return_value="a"):
        response = await handler.request_approval(request_payload)

    assert response.approved is True


@pytest.mark.asyncio
async def test_cli_rejection(request_payload: EscalationRequest) -> None:
    handler = CLIEscalation(timeout_seconds=10)

    with patch("builtins.input", return_value="r"):
        response = await handler.request_approval(request_payload)

    assert response.approved is False
    assert "Rechazado" in response.reason


@pytest.mark.asyncio
async def test_cli_cancel(request_payload: EscalationRequest) -> None:
    handler = CLIEscalation(timeout_seconds=10)

    with patch("builtins.input", return_value="c"):
        response = await handler.request_approval(request_payload)

    assert response.approved is False


@pytest.mark.asyncio
async def test_cli_invalid_input(request_payload: EscalationRequest) -> None:
    handler = CLIEscalation(timeout_seconds=10)

    with patch("builtins.input", return_value="x"):
        response = await handler.request_approval(request_payload)

    assert response.approved is False
    assert "inválida" in response.reason


@pytest.mark.asyncio
async def test_cli_timeout() -> None:
    handler = CLIEscalation(timeout_seconds=0)

    async def slow_input(prompt: str) -> str:
        await asyncio.sleep(1)
        return "a"

    with patch.object(handler, "_read_input", slow_input):
        with pytest.raises(EscalationTimeout):
            await handler.request_approval(EscalationRequest(timeout_seconds=0))


def test_approval_response_defaults() -> None:
    response = ApprovalResponse(approved=True)
    assert response.approved is True
    assert response.reason == ""
    assert response.approver == "human"


def test_escalation_request_has_uuid() -> None:
    req1 = EscalationRequest()
    req2 = EscalationRequest()
    assert req1.approval_id != req2.approval_id
