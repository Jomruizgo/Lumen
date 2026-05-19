"""Tests para capabilities cli.*."""

from __future__ import annotations

import sys

import pytest

from lumen.stdlib.base import ExecutionContext
from lumen.stdlib.cli.capabilities import CliPipe, CliRun, CliWrap


@pytest.fixture
def ctx() -> ExecutionContext:
    return ExecutionContext(mode="fast")


@pytest.mark.asyncio
async def test_cli_run_success(ctx: ExecutionContext) -> None:
    cap = CliRun()
    if sys.platform == "win32":
        result = await cap.execute({"command": "cmd", "args": ["/c", "echo", "hello"]}, ctx)
    else:
        result = await cap.execute({"command": "echo", "args": ["hello"]}, ctx)
    assert result.success
    assert "hello" in result.value["stdout"]


@pytest.mark.asyncio
async def test_cli_run_command_not_found(ctx: ExecutionContext) -> None:
    cap = CliRun()
    result = await cap.execute({"command": "nonexistent_binary_xyz"}, ctx)
    assert not result.success
    assert "no encontrado" in result.error.lower()


@pytest.mark.asyncio
async def test_cli_run_no_command(ctx: ExecutionContext) -> None:
    cap = CliRun()
    result = await cap.execute({}, ctx)
    assert not result.success


@pytest.mark.asyncio
async def test_cli_run_timeout(ctx: ExecutionContext) -> None:
    cap = CliRun()
    if sys.platform == "win32":
        cmd = "cmd"
        args = ["/c", "ping", "-n", "5", "127.0.0.1"]
    else:
        cmd = "sleep"
        args = ["5"]
    result = await cap.execute({"command": cmd, "args": args, "timeout": 0.1}, ctx)
    assert not result.success
    assert "excedió" in result.error.lower()


@pytest.mark.asyncio
async def test_cli_pipe_success(ctx: ExecutionContext) -> None:
    if sys.platform == "win32":
        pytest.skip("pipe test no compatible con Windows en este contexto")

    cap = CliPipe()
    result = await cap.execute(
        {"commands": [["echo", "hello world"], ["grep", "hello"]]}, ctx
    )
    assert result.success
    assert "hello" in result.value["stdout"]


@pytest.mark.asyncio
async def test_cli_pipe_no_commands(ctx: ExecutionContext) -> None:
    cap = CliPipe()
    result = await cap.execute({"commands": []}, ctx)
    assert not result.success


@pytest.mark.asyncio
async def test_cli_wrap_git(ctx: ExecutionContext) -> None:
    import shutil

    if not shutil.which("git"):
        pytest.skip("git no disponible")

    cap = CliWrap()
    result = await cap.execute({"binary_path": "git"}, ctx)
    assert result.success
    assert result.value["binary"] == "git"


@pytest.mark.asyncio
async def test_cli_wrap_no_binary(ctx: ExecutionContext) -> None:
    cap = CliWrap()
    result = await cap.execute({}, ctx)
    assert not result.success


def test_cli_run_describe() -> None:
    cap = CliRun()
    desc = cap.describe()
    assert "cli.run" in desc.name
    assert "command" in desc.signature.lower()


def test_cli_wrap_describe() -> None:
    cap = CliWrap()
    desc = cap.describe()
    assert "cli.wrap" in desc.name
