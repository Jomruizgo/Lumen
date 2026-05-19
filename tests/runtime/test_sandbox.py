"""Tests para el sandbox de ejecución."""

from __future__ import annotations

import pytest

from lumen.runtime.sandbox import Sandbox, SandboxTimeout


@pytest.mark.asyncio
async def test_runs_program_in_subprocess() -> None:
    sandbox = Sandbox(timeout_seconds=10)
    result = await sandbox.run(
        program_source='@lumen 1.0\nprint "Hello"',
        compiled_data={"mode": "fast", "capabilities": []},
    )
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_capability_whitelist_enforced() -> None:
    sandbox = Sandbox(
        capability_whitelist=["comm.email"],
        timeout_seconds=10,
    )
    result = await sandbox.run(
        program_source='@lumen 1.0\ntransfer.money(...)',
        compiled_data={"mode": "safe", "capabilities": ["sensitive.transfer"]},
    )
    assert result.exit_code != 0
    assert "LMN-0001" in result.stderr


@pytest.mark.asyncio
async def test_capability_whitelist_passes_authorized() -> None:
    sandbox = Sandbox(
        capability_whitelist=["comm.email"],
        timeout_seconds=10,
    )
    result = await sandbox.run(
        program_source='@lumen 1.0\nread.email(since="yesterday")',
        compiled_data={"mode": "fast", "capabilities": ["comm.email"]},
    )
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_timeout_kills_runaway() -> None:
    sandbox = Sandbox(timeout_seconds=0.5)
    with pytest.raises(SandboxTimeout):
        await sandbox.run(
            program_source="@lumen 1.0\nwhile true: pass",
            compiled_data={"mode": "fast", "capabilities": [], "_infinite_loop": True},
        )


@pytest.mark.asyncio
async def test_captures_output_structured() -> None:
    sandbox = Sandbox(timeout_seconds=10)
    result = await sandbox.run(
        program_source='@lumen 1.0\nprint "hello"',
        compiled_data={"mode": "fast", "capabilities": []},
    )
    assert "mode" in result.structured_output


def test_check_whitelist_empty_allows_all() -> None:
    sandbox = Sandbox(capability_whitelist=[])
    unauthorized = sandbox.check_whitelist(["comm.email", "sensitive.transfer"])
    assert unauthorized == []


def test_check_whitelist_detects_unauthorized() -> None:
    sandbox = Sandbox(capability_whitelist=["comm.email"])
    unauthorized = sandbox.check_whitelist(["comm.email", "sensitive.transfer"])
    assert "sensitive.transfer" in unauthorized
    assert "comm.email" not in unauthorized
