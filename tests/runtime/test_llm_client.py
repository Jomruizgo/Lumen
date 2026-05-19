"""Tests para el cliente LLM."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from lumen.runtime.llm_client import LLMClient, LLMConfig, Resolution


@pytest.fixture
def llm_client(tmp_path: Path) -> LLMClient:
    config = LLMConfig(command="echo", args=[], timeout_seconds=5, max_retries=1)
    return LLMClient(config=config, cache_dir=tmp_path / "cache")


@pytest.fixture
def mock_resolution() -> str:
    return json.dumps({"value": "Pedro García", "confidence": 0.95, "strategy": "high_confidence"})


@pytest.mark.asyncio
async def test_invokes_configured_cli(llm_client: LLMClient, mock_resolution: str) -> None:
    async def fake_invoke(prompt: str) -> str:
        return mock_resolution

    with patch.object(llm_client, "_invoke_llm", side_effect=fake_invoke):
        result = await llm_client.resolve(
            "Pedro García",
            {"context": "crm"},
            ["high_confidence", "ambiguous", "unknown"],
        )

    assert result.value == "Pedro García"
    assert result.confidence == pytest.approx(0.95)
    assert result.strategy_used == "high_confidence"


@pytest.mark.asyncio
async def test_caches_resolutions(llm_client: LLMClient, mock_resolution: str) -> None:
    call_count = 0

    async def fake_invoke(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        return mock_resolution

    with patch.object(llm_client, "_invoke_llm", side_effect=fake_invoke):
        await llm_client.resolve("test", {}, ["high_confidence"])
        await llm_client.resolve("test", {}, ["high_confidence"])

    assert call_count == 1


@pytest.mark.asyncio
async def test_retries_on_failure(llm_client: LLMClient) -> None:
    call_count = 0

    async def failing_invoke(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("LLM unavailable")

    with patch.object(llm_client, "_invoke_llm", side_effect=failing_invoke):
        with patch.object(llm_client, "_fallback", return_value=Resolution("", 0.0, "fail_safe")):
            result = await llm_client.resolve("test", {}, ["high_confidence"])

    assert call_count == llm_client.config.max_retries + 1
    assert result.strategy_used == "fail_safe"


@pytest.mark.asyncio
async def test_fallback_when_unavailable(llm_client: LLMClient) -> None:
    import asyncio

    async def timeout_invoke(prompt: str) -> str:
        raise asyncio.TimeoutError()

    with patch.object(llm_client, "_invoke_llm", side_effect=timeout_invoke):
        result = await llm_client.resolve("test", {}, ["high_confidence"])

    assert result.strategy_used == "fail_safe"
    assert result.confidence == 0.0


def test_parse_response_valid_json(llm_client: LLMClient) -> None:
    raw = '{"value": "Engineering", "confidence": 0.92, "strategy": "high_confidence"}'
    res = llm_client._parse_response(raw, ["high_confidence", "ambiguous"])
    assert res.value == "Engineering"
    assert res.confidence == pytest.approx(0.92)


def test_parse_response_invalid_json(llm_client: LLMClient) -> None:
    res = llm_client._parse_response("not json at all", ["high_confidence"])
    assert res.strategy_used == "unknown"
    assert res.confidence == 0.0


def test_build_prompt_contains_ambiguous(llm_client: LLMClient) -> None:
    prompt = llm_client._build_prompt("Pedro García", {"crm": "data"}, ["high_confidence"])
    assert "Pedro García" in prompt
    assert "high_confidence" in prompt
