"""Tests para el agent runtime."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from lumen.runtime.agent_runtime import AgentAlreadyRunningError, AgentRuntime, AgentState


@pytest.fixture
def agent_runtime(tmp_path: Path) -> AgentRuntime:
    return AgentRuntime(agents_dir=tmp_path / "agents")


@pytest.mark.asyncio
async def test_starts_agent_as_subprocess(agent_runtime: AgentRuntime) -> None:
    state = await agent_runtime.start(
        name="test_agent",
        program_source='@lumen 1.0\nprint "hello"',
        agent_config={"poll_interval_seconds": 1},
    )
    assert state.status == "running"
    assert state.pid is not None
    assert state.pid > 0
    await agent_runtime.stop("test_agent")


@pytest.mark.asyncio
async def test_stop_kills_subprocess(agent_runtime: AgentRuntime) -> None:
    await agent_runtime.start(
        name="to_stop",
        program_source='@lumen 1.0',
        agent_config={"poll_interval_seconds": 60},
    )
    state = await agent_runtime.stop("to_stop")
    assert state.status == "stopped"
    assert state.pid is None


@pytest.mark.asyncio
async def test_status_reports_running(agent_runtime: AgentRuntime) -> None:
    await agent_runtime.start(
        name="status_test",
        program_source='@lumen 1.0',
        agent_config={"poll_interval_seconds": 60},
    )
    state = agent_runtime.status("status_test")
    assert state.status == "running"
    await agent_runtime.stop("status_test")


@pytest.mark.asyncio
async def test_persists_state_between_checks(agent_runtime: AgentRuntime) -> None:
    await agent_runtime.start(
        name="persist_test",
        program_source='@lumen 1.0',
        agent_config={"poll_interval_seconds": 60},
    )
    state1 = agent_runtime.status("persist_test")

    new_runtime = AgentRuntime(agents_dir=agent_runtime._dir)
    state2 = new_runtime.status("persist_test")

    assert state1.pid == state2.pid
    await agent_runtime.stop("persist_test")


@pytest.mark.asyncio
async def test_logs_after_start(agent_runtime: AgentRuntime) -> None:
    await agent_runtime.start(
        name="log_test",
        program_source='@lumen 1.0',
        agent_config={"poll_interval_seconds": 1},
    )
    await asyncio.sleep(1.5)
    logs = agent_runtime.logs("log_test")
    await agent_runtime.stop("log_test")
    assert isinstance(logs, list)


def test_status_stopped_agent(agent_runtime: AgentRuntime) -> None:
    state = agent_runtime.status("nonexistent")
    assert state.status == "stopped"
    assert state.pid is None
