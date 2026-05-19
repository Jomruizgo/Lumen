"""CLI principal de Lumen."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

app = typer.Typer(
    name="lumen",
    help="Lumen — lenguaje de programación con modos fast/safe/flow",
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        from lumen import __version__
        typer.echo(f"Lumen {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help="Muestra la versión de Lumen",
    ),
) -> None:
    pass


@app.command()
def run(
    file: str = typer.Argument(..., help="Archivo .lumen a ejecutar"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simular sin ejecutar"),
    check_only: bool = typer.Option(False, "--check-only", help="Solo compilar, no ejecutar"),
) -> None:
    """Ejecuta un programa Lumen."""
    source_path = Path(file)
    if not source_path.exists():
        typer.echo(f"[ERROR] Archivo no encontrado: {file}", err=True)
        raise typer.Exit(1)

    source = source_path.read_text(encoding="utf-8")

    if dry_run:
        from lumen.tooling.dryrun import dry_run as do_dry_run
        plan = do_dry_run(source)
        typer.echo(plan.to_text())
        return

    if check_only:
        from lumen.compiler.pipeline import CompilerPipeline
        result = CompilerPipeline().compile(source)
        if not result.ok:
            for err in result.errors:
                typer.echo(f"[{err.code}] línea {err.line}:{err.col} — {err.message}", err=True)
            raise typer.Exit(1)
        typer.echo(f"[OK] {file} compila correctamente (modo: {result.program.mode if result.program else 'unknown'})")
        return

    import asyncio
    from lumen.compiler.pipeline import CompilerPipeline
    from lumen.runtime.interpreter import Interpreter
    from lumen.stdlib.base import ExecutionContext

    compile_result = CompilerPipeline().compile(source)
    if not compile_result.ok:
        for err in compile_result.errors:
            typer.echo(f"[{err.code}] línea {err.line}:{err.col} — {err.message}", err=True)
        raise typer.Exit(1)

    async def _run() -> None:
        ctx = ExecutionContext(mode=compile_result.program.mode if compile_result.program else "fast")
        interp = Interpreter(context=ctx)
        exec_result = await interp.run(compile_result.program)
        if exec_result.output:
            typer.echo(exec_result.output)
        if not exec_result.success:
            typer.echo(f"[ERROR] {exec_result.error}", err=True)
            raise typer.Exit(1)

    asyncio.run(_run())


@app.command()
def fmt(
    file: str = typer.Argument(..., help="Archivo .lumen a formatear"),
    check: bool = typer.Option(False, "--check", help="Verificar formato sin modificar"),
) -> None:
    """Formatea un archivo Lumen (formato único, idempotente)."""
    from lumen.tooling.format import check_format, format_source

    source_path = Path(file)
    if not source_path.exists():
        typer.echo(f"[ERROR] Archivo no encontrado: {file}", err=True)
        raise typer.Exit(1)

    source = source_path.read_text(encoding="utf-8")
    formatted = format_source(source)

    if check:
        if formatted == source:
            typer.echo(f"[OK] {file} ya está formateado correctamente")
        else:
            typer.echo(f"[FAIL] {file} no está formateado. Ejecuta: lumen fmt {file}", err=True)
            raise typer.Exit(1)
    else:
        source_path.write_text(formatted, encoding="utf-8")
        typer.echo(f"[OK] {file} formateado")


@app.command()
def explain(
    file: str = typer.Argument(..., help="Archivo .lumen a explicar"),
) -> None:
    """Explica un programa Lumen en lenguaje natural."""
    from lumen.tooling.explain import explain as do_explain

    source_path = Path(file)
    if not source_path.exists():
        typer.echo(f"[ERROR] Archivo no encontrado: {file}", err=True)
        raise typer.Exit(1)

    source = source_path.read_text(encoding="utf-8")
    explanation = do_explain(source)
    typer.echo(explanation.to_text())


agent_app = typer.Typer(help="Gestión de agentes Lumen (modo flow)")
app.add_typer(agent_app, name="agent")


@agent_app.command("start")
def agent_start(
    name: str = typer.Argument(..., help="Nombre del agent"),
    file: str = typer.Option(..., "--file", "-f", help="Archivo .lumen del agent"),
) -> None:
    """Inicia un agent como proceso persistente."""
    import asyncio
    from lumen.runtime.agent_runtime import AgentRuntime

    source_path = Path(file)
    if not source_path.exists():
        typer.echo(f"[ERROR] Archivo no encontrado: {file}", err=True)
        raise typer.Exit(1)

    source = source_path.read_text(encoding="utf-8")
    runtime = AgentRuntime()

    async def _start() -> None:
        state = await runtime.start(name=name, program_source=source)
        typer.echo(f"[OK] Agent {name!r} iniciado (PID {state.pid})")

    asyncio.run(_start())


@agent_app.command("stop")
def agent_stop(name: str = typer.Argument(..., help="Nombre del agent")) -> None:
    """Detiene un agent."""
    import asyncio
    from lumen.runtime.agent_runtime import AgentRuntime

    runtime = AgentRuntime()

    async def _stop() -> None:
        state = await runtime.stop(name)
        typer.echo(f"[OK] Agent {name!r} detenido")

    asyncio.run(_stop())


@agent_app.command("status")
def agent_status(name: str = typer.Argument(..., help="Nombre del agent")) -> None:
    """Estado de un agent."""
    from lumen.runtime.agent_runtime import AgentRuntime

    runtime = AgentRuntime()
    state = runtime.status(name)
    typer.echo(f"Agent {name!r}: {state.status} (PID: {state.pid})")
    if state.started_at:
        typer.echo(f"  Iniciado: {state.started_at}")
    if state.restart_count:
        typer.echo(f"  Reinicios: {state.restart_count}")
    if state.last_error:
        typer.echo(f"  Último error: {state.last_error}")


@agent_app.command("logs")
def agent_logs(
    name: str = typer.Argument(..., help="Nombre del agent"),
    lines: int = typer.Option(50, "--lines", "-n", help="Últimas N líneas"),
) -> None:
    """Muestra los logs de un agent."""
    from lumen.runtime.agent_runtime import AgentRuntime

    runtime = AgentRuntime()
    log_lines = runtime.logs(name, last_n=lines)
    if not log_lines:
        typer.echo(f"[INFO] No hay logs para agent {name!r}")
    else:
        typer.echo("\n".join(log_lines))


if __name__ == "__main__":
    app()
