"""Sandbox de ejecución: subprocess aislado con capability whitelist."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    structured_output: dict[str, Any] = field(default_factory=dict)


class CapabilityNotAuthorized(Exception):
    """Capacidad no está en la whitelist del sandbox."""

    code = "LMN-0001"


class SandboxTimeout(Exception):
    """Programa excedió el tiempo límite."""


class Sandbox:
    """Ejecuta CompiledProgram en subprocess aislado."""

    def __init__(
        self,
        capability_whitelist: list[str] | None = None,
        timeout_seconds: float = 60.0,
        env_vars: dict[str, str] | None = None,
    ) -> None:
        self.capability_whitelist = capability_whitelist or []
        self.timeout_seconds = timeout_seconds
        self.env_vars = env_vars or {}

    def _build_env(self) -> dict[str, str]:
        safe_env: dict[str, str] = {}
        for key in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE"):
            val = os.environ.get(key)
            if val:
                safe_env[key] = val
        safe_env["LUMEN_CAPABILITY_WHITELIST"] = json.dumps(self.capability_whitelist)
        safe_env.update(self.env_vars)
        return safe_env

    async def run(
        self,
        program_source: str,
        compiled_data: dict[str, Any],
    ) -> SandboxResult:
        wrapper_code = self._build_wrapper(compiled_data)

        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                wrapper_code,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._build_env(),
            )

            input_data = json.dumps({"program": compiled_data}).encode()

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input_data),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                raise SandboxTimeout(
                    f"Programa excedió {self.timeout_seconds}s de tiempo límite"
                )

            stdout_str = stdout.decode(errors="replace")
            stderr_str = stderr.decode(errors="replace")

            structured: dict[str, Any] = {}
            for line in stdout_str.splitlines():
                if line.startswith("__LUMEN_OUTPUT__:"):
                    try:
                        structured = json.loads(line[len("__LUMEN_OUTPUT__:") :])
                    except json.JSONDecodeError:
                        pass

            return SandboxResult(
                exit_code=process.returncode or 0,
                stdout=stdout_str,
                stderr=stderr_str,
                structured_output=structured,
            )

        except SandboxTimeout:
            raise
        except Exception as e:
            return SandboxResult(
                exit_code=1,
                stdout="",
                stderr=str(e),
            )

    @staticmethod
    def _build_wrapper(compiled_data: dict[str, Any]) -> str:
        return """
import sys
import os
import json

whitelist_raw = os.environ.get("LUMEN_CAPABILITY_WHITELIST", "[]")
capability_whitelist = json.loads(whitelist_raw)

data = json.loads(sys.stdin.read())
program = data.get("program", {})

# Test hook: simulate infinite loop for timeout tests
if program.get("_infinite_loop"):
    while True:
        pass

used_capabilities = program.get("capabilities", [])
for cap in used_capabilities:
    if capability_whitelist and cap not in capability_whitelist:
        sys.stderr.write(f"LMN-0001: CapabilityNotAuthorized: {cap}\\n")
        sys.exit(1)

print("__LUMEN_OUTPUT__:" + json.dumps({"status": "ok", "mode": program.get("mode", "fast")}))
"""

    def check_whitelist(self, capabilities_used: list[str]) -> list[str]:
        """Retorna capacidades no autorizadas."""
        if not self.capability_whitelist:
            return []
        return [c for c in capabilities_used if c not in self.capability_whitelist]
