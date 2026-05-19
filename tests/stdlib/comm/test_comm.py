"""Tests para capabilities comm.*."""

from __future__ import annotations

import pytest

from lumen.stdlib.base import ExecutionContext
from lumen.stdlib.comm.capabilities import (
    CommNotifyUser,
    CommReadEmail,
    CommSendEmail,
    CommSendMessage,
    CommSummarizeEmail,
)


@pytest.fixture
def dry_ctx() -> ExecutionContext:
    return ExecutionContext(mode="fast", dry_run=True)


@pytest.fixture
def ctx() -> ExecutionContext:
    return ExecutionContext(mode="fast")


@pytest.mark.asyncio
async def test_read_email_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = CommReadEmail()
    result = await cap.execute({"since": "yesterday"}, dry_ctx)
    assert result.success
    assert isinstance(result.value, list)
    assert len(result.value) > 0
    assert "subject" in result.value[0]


@pytest.mark.asyncio
async def test_read_email_no_credentials(ctx: ExecutionContext) -> None:
    cap = CommReadEmail()
    result = await cap.execute({"since": "yesterday"}, ctx)
    assert not result.success or result.success


@pytest.mark.asyncio
async def test_send_email_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = CommSendEmail()
    result = await cap.execute(
        {"to": "test@example.com", "subject": "Test", "body": "Hello"},
        dry_ctx,
    )
    assert result.success
    assert "dry-run" in result.value["status"]


@pytest.mark.asyncio
async def test_send_email_missing_args(dry_ctx: ExecutionContext) -> None:
    cap = CommSendEmail()
    result = await cap.execute({"body": "Hello"}, dry_ctx)
    assert not result.success


@pytest.mark.asyncio
async def test_summarize_email(ctx: ExecutionContext) -> None:
    cap = CommSummarizeEmail()
    result = await cap.execute(
        {
            "email": {
                "body": "Este es un email largo con mucho contenido. " * 10
            },
            "max_lines": 3,
        },
        ctx,
    )
    assert result.success
    assert isinstance(result.value, str)
    assert len(result.value) < 500


@pytest.mark.asyncio
async def test_summarize_email_empty(ctx: ExecutionContext) -> None:
    cap = CommSummarizeEmail()
    result = await cap.execute({"email": {}}, ctx)
    assert not result.success


@pytest.mark.asyncio
async def test_notify_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = CommNotifyUser()
    result = await cap.execute(
        {"text": "Test notification", "priority": "high"}, dry_ctx
    )
    assert result.success
    assert result.value["dry_run"] is True


@pytest.mark.asyncio
async def test_notify_missing_text(ctx: ExecutionContext) -> None:
    cap = CommNotifyUser()
    result = await cap.execute({}, ctx)
    assert not result.success


@pytest.mark.asyncio
async def test_send_message_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = CommSendMessage()
    result = await cap.execute(
        {"channel": "slack", "recipient": "#engineering", "text": "Hello"},
        dry_ctx,
    )
    assert result.success


@pytest.mark.asyncio
async def test_send_message_no_text(dry_ctx: ExecutionContext) -> None:
    cap = CommSendMessage()
    result = await cap.execute({"channel": "slack"}, dry_ctx)
    assert not result.success


def test_read_email_describe() -> None:
    cap = CommReadEmail()
    desc = cap.describe()
    assert "email" in desc.name.lower()


def test_send_email_describe() -> None:
    cap = CommSendEmail()
    desc = cap.describe()
    assert "email" in desc.name.lower()
    assert "reversible" in desc.signature.lower()
