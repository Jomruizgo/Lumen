"""Script de build para generar binario lumen standalone en Linux.

Si PyInstaller está disponible, genera un ELF standalone verdadero.
Si no, genera un wrapper shell script que requiere Python instalado.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import zipapp
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def _has_pyinstaller() -> bool:
    return importlib.util.find_spec("PyInstaller") is not None


def _build_with_pyinstaller(build_dir: Path) -> None:
    print("[lumen] Generando ELF standalone con PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--name", "lumen",
        "--distpath", str(build_dir),
        "--workpath", str(build_dir / "_pyinstaller"),
        "--specpath", str(Path(__file__).parent),
        "--hidden-import", "lumen",
        "--hidden-import", "lumen.cli",
        "--hidden-import", "lark",
        "--hidden-import", "pydantic",
        "--hidden-import", "typer",
        str(ROOT / "lumen" / "cli.py"),
    ]
    result = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if result.returncode != 0:
        print("[ERROR] PyInstaller falló", file=sys.stderr)
        sys.exit(result.returncode)


def _build_shell_wrapper(build_dir: Path) -> None:
    """Crea un wrapper shell script (requiere Python en PATH)."""
    print("[lumen] PyInstaller no disponible — generando wrapper shell script...")

    # Crear un .pyz con zipapp
    tmp = Path(__file__).parent / "_tmp_app"
    tmp.mkdir(exist_ok=True)
    (tmp / "__main__.py").write_text(
        "from lumen.cli import app\napp()\n", encoding="utf-8"
    )
    pyz = build_dir / "lumen.pyz"
    zipapp.create_archive(str(tmp), str(pyz), interpreter=sys.executable)
    shutil.rmtree(tmp, ignore_errors=True)

    # Shell script wrapper
    wrapper = build_dir / "lumen"
    python_exe = sys.executable
    wrapper.write_text(
        f"#!/bin/sh\nexec '{python_exe}' '{pyz}' \"$@\"\n", encoding="utf-8"
    )
    wrapper.chmod(0o755)
    print(f"[OK] Wrapper shell script creado: {wrapper}")


def build() -> None:
    build_dir = Path(__file__).parent / "build"
    build_dir.mkdir(exist_ok=True)

    if _has_pyinstaller():
        _build_with_pyinstaller(build_dir)
    else:
        _build_shell_wrapper(build_dir)

    binary = build_dir / "lumen"
    if not binary.exists():
        print("[ERROR] No se generó el binario lumen", file=sys.stderr)
        sys.exit(1)

    binary.chmod(0o755)
    print(f"[OK] Generado: {binary}")

    # Verificar versión
    result = subprocess.run(
        [sys.executable, "-m", "lumen.cli", "--version"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    version_out = result.stdout.strip()
    if version_out:
        print(f"[OK] Versión verificada: {version_out}")
    else:
        print("[WARN] No se pudo verificar la versión via CLI")


if __name__ == "__main__":
    build()
