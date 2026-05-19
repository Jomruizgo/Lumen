"""Agent runtime: subprocesses persistentes para agents de modo flow."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _get_agents_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Lumen" / "agents"
    return Path.home() / ".lumen" / "agents"


@dataclass
class AgentState:
    name: str
    pid: int | None = None
    status: str = "stopped"
    started_at: str = ""
    restart_count: int = 0
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "pid": self.pid,
            "status": self.status,
            "started_at": self.started_at,
            "restart_count": self.restart_count,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentState:
        return cls(
            name=str(data.get("name", "")),
            pid=data.get("pid"),
            status=str(data.get("status", "stopped")),
            started_at=str(data.get("started_at", "")),
            restart_count=int(data.get("restart_count", 0)),
            last_error=str(data.get("last_error", "")),
        )


class AgentNotFoundError(Exception):
    pass


class AgentAlreadyRunningError(Exception):
    pass


class AgentRuntime:
    """Gestión de agents como subprocesses persistentes."""

    MAX_RESTARTS_PER_HOUR = 3

    def __init__(self, agents_dir: Path | None = None) -> None:
        self._dir = agents_dir or _get_agents_dir()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    def _agent_dir(self, name: str) -> Path:
        d = self._dir / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _state_path(self, name: str) -> Path:
        return self._agent_dir(name) / "state.json"

    def _load_state(self, name: str) -> AgentState:
        path = self._state_path(name)
        if not path.exists():
            return AgentState(name=name)
        try:
            with open(path, encoding="utf-8") as f:
                return AgentState.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError):
            return AgentState(name=name)

    def _save_state(self, state: AgentState) -> None:
        path = self._state_path(state.name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)

    async def start(
        self,
        name: str,
        program_source: str,
        agent_config: dict[str, Any] | None = None,
    ) -> AgentState:
        state = self._load_state(name)
        if state.status == "running" and state.pid is not None:
            try:
                os.kill(state.pid, 0)
                raise AgentAlreadyRunningError(f"Agent {name!r} ya está corriendo (PID {state.pid})")
            except ProcessLookupError:
                pass

        script = self._build_agent_script(name, program_source, agent_config or {})
        agent_script_path = self._agent_dir(name) / "agent_loop.py"
        agent_script_path.write_text(script, encoding="utf-8")

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(agent_script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._agent_dir(name)),
        )
        self._processes[name] = proc

        state = AgentState(
            name=name,
            pid=proc.pid,
            status="running",
            started_at=datetime.now(UTC).isoformat(),
        )
        self._save_state(state)

        asyncio.create_task(self._monitor(name, proc))
        return state

    async def stop(self, name: str) -> AgentState:
        state = self._load_state(name)
        proc = self._processes.get(name)

        if proc is not None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            del self._processes[name]
        elif state.pid is not None:
            try:
                os.kill(state.pid, 15)
            except ProcessLookupError:
                pass

        state.status = "stopped"
        state.pid = None
        self._save_state(state)
        return state

    def status(self, name: str) -> AgentState:
        state = self._load_state(name)
        if state.pid is not None:
            try:
                os.kill(state.pid, 0)
                state.status = "running"
            except ProcessLookupError:
                state.status = "crashed"
        return state

    def logs(self, name: str, last_n: int = 100) -> list[str]:
        log_path = self._agent_dir(name) / "agent.log"
        if not log_path.exists():
            return []
        lines = log_path.read_text(encoding="utf-8").splitlines()
        return lines[-last_n:]

    async def _monitor(
        self, name: str, proc: asyncio.subprocess.Process
    ) -> None:
        try:
            await proc.wait()
        except asyncio.CancelledError:
            return

        state = self._load_state(name)
        if state.status != "running":
            return

        state.last_error = f"Agent terminó con exit code {proc.returncode}"
        state.status = "crashed"
        self._save_state(state)

    @staticmethod
    def _build_agent_script(
        name: str, program_source: str, config: dict[str, Any]
    ) -> str:
        poll_interval = config.get("poll_interval_seconds", 300)
        return f"""
import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

AGENT_NAME = {name!r}
PROGRAM_SOURCE = {program_source!r}
POLL_INTERVAL = {poll_interval}
LOG_PATH = Path("agent.log")

def log(msg):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{{ts}}] {{msg}}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\\n")

async def main():
    log(f"Agent {{AGENT_NAME}} iniciado")
    while True:
        try:
            log("Ciclo de poll")
            await asyncio.sleep(POLL_INTERVAL)
        except asyncio.CancelledError:
            log("Agent detenido")
            break
        except Exception as e:
            log(f"Error: {{e}}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
"""
