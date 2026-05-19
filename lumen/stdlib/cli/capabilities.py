"""Capacidades cli.*: run, pipe, wrap."""

from __future__ import annotations

import asyncio
import shlex
import subprocess
from typing import Any

from lumen.stdlib.base import (
    Capability,
    CapabilityDescription,
    CapabilityRegistry,
    ExecutionContext,
    Result,
)


class CliRun(Capability):
    name = "cli.run"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        command: str = args.get("command", "")
        cmd_args: list[str] = args.get("args", [])
        timeout: float = float(args.get("timeout", 30.0))

        if not command:
            return Result.fail("cli.run requiere el argumento 'command'")

        full_cmd = [command] + [str(a) for a in cmd_args]

        try:
            proc = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            if proc.returncode == 0:
                return Result.ok(
                    {
                        "stdout": stdout.decode(errors="replace"),
                        "stderr": stderr.decode(errors="replace"),
                        "exit_code": proc.returncode,
                    }
                )
            return Result.fail(
                f"Comando falló con exit code {proc.returncode}: {stderr.decode(errors='replace')}"
            )
        except asyncio.TimeoutError:
            return Result.fail(f"Comando excedió {timeout}s")
        except FileNotFoundError:
            return Result.fail(f"Comando no encontrado: {command!r}")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="cli.run(command: text, args: List<text> = [], timeout: number = 30) -> Output",
            description="Ejecuta un comando CLI en subprocess y captura stdout/stderr.",
            examples=['cli.run("git", args=["status"])', 'cli.run("ffmpeg", args=["-i", "input.mp4"])'],
        )


class CliPipe(Capability):
    name = "cli.pipe"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        commands: list[list[str]] = args.get("commands", [])
        timeout: float = float(args.get("timeout", 30.0))

        if not commands:
            return Result.fail("cli.pipe requiere 'commands'")

        try:
            procs: list[asyncio.subprocess.Process] = []
            prev_stdout = None

            for cmd in commands:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=prev_stdout,  # type: ignore[arg-type]
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                procs.append(proc)
                prev_stdout = proc.stdout

            last = procs[-1]
            stdout, stderr = await asyncio.wait_for(
                last.communicate(), timeout=timeout
            )

            for p in procs[:-1]:
                await p.wait()

            if last.returncode == 0:
                return Result.ok({"stdout": stdout.decode(errors="replace")})
            return Result.fail(
                f"Pipeline falló: {stderr.decode(errors='replace')}"
            )
        except asyncio.TimeoutError:
            return Result.fail(f"Pipeline excedió {timeout}s")

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="cli.pipe(commands: List<List<text>>) -> Output",
            description="Ejecuta un pipeline de comandos conectados por pipes.",
            examples=['cli.pipe([["cat", "file.txt"], ["grep", "error"], ["wc", "-l"]])'],
        )


class CliWrap(Capability):
    name = "cli.wrap"
    mode = "fast"
    reversible = False
    requires_approval = False

    async def execute(self, args: dict[str, Any], context: ExecutionContext) -> Result:
        binary_path: str = args.get("binary_path", "")
        if not binary_path:
            return Result.fail("cli.wrap requiere 'binary_path'")

        subcommands = await self._extract_subcommands(binary_path)
        return Result.ok(
            {
                "binary": binary_path,
                "subcommands": subcommands,
                "description": f"Wrapped CLI: {binary_path}",
            }
        )

    @staticmethod
    async def _extract_subcommands(binary: str) -> list[str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                binary, "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            output = (stdout + stderr).decode(errors="replace")
            import re

            subcommands = re.findall(r"^\s{2,4}(\w[\w-]+)\s+\w", output, re.MULTILINE)
            return list(dict.fromkeys(subcommands))[:20]
        except Exception:
            return []

    def describe(self) -> CapabilityDescription:
        return CapabilityDescription(
            name=self.name,
            signature="cli.wrap(binary_path: text) -> Capability",
            description="Crea una capability dinámica a partir de un binario CLI.",
            examples=['git_cap = cli.wrap("git")', 'docker_cap = cli.wrap("docker")'],
        )
