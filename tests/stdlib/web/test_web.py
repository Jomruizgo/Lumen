"""Tests para capabilities web.*."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lumen.stdlib.base import ExecutionContext
from lumen.stdlib.web.capabilities import WebFetch, WebPost


@pytest.fixture
def ctx() -> ExecutionContext:
    return ExecutionContext(mode="fast")


@pytest.fixture
def dry_ctx() -> ExecutionContext:
    return ExecutionContext(mode="fast", dry_run=True)


@pytest.mark.asyncio
async def test_fetch_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = WebFetch()
    result = await cap.execute({"url": "https://example.com"}, dry_ctx)
    assert result.success
    assert result.value.get("dry_run") is not False or "[dry-run]" in str(result.value)


@pytest.mark.asyncio
async def test_fetch_no_url(ctx: ExecutionContext) -> None:
    cap = WebFetch()
    result = await cap.execute({}, ctx)
    assert not result.success
    assert "url" in result.error.lower()


@pytest.mark.asyncio
async def test_fetch_success(ctx: ExecutionContext) -> None:
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"key": "value"}'
    mock_response.headers = {"content-type": "application/json"}
    mock_response.url = "https://example.com"

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        cap = WebFetch()
        result = await cap.execute({"url": "https://example.com"}, ctx)

    assert result.success
    assert result.value["status"] == 200


@pytest.mark.asyncio
async def test_post_dry_run(dry_ctx: ExecutionContext) -> None:
    cap = WebPost()
    result = await cap.execute(
        {"url": "https://example.com/api", "body": {"key": "value"}}, dry_ctx
    )
    assert result.success


@pytest.mark.asyncio
async def test_post_no_url(ctx: ExecutionContext) -> None:
    cap = WebPost()
    result = await cap.execute({"body": {}}, ctx)
    assert not result.success


@pytest.mark.asyncio
async def test_post_success(ctx: ExecutionContext) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.text = '{"created": true}'
    mock_response.headers = {}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        cap = WebPost()
        result = await cap.execute(
            {"url": "https://example.com/api", "body": {"data": "test"}}, ctx
        )

    assert result.success
    assert result.value["status"] == 201


def test_fetch_describe() -> None:
    cap = WebFetch()
    desc = cap.describe()
    assert "web.fetch" in desc.name
    assert "url" in desc.signature.lower()


def test_post_describe() -> None:
    cap = WebPost()
    desc = cap.describe()
    assert "web.post" in desc.name
