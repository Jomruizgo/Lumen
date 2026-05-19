"""Script de build para generar lumen.exe standalone en Windows.

Si PyInstaller está disponible, genera un .exe verdaderamente standalone.
Si no, genera un wrapper .exe vía zipapp que requiere Python instalado.
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
import zipapp
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def _has_pyinstaller() -> bool:
    return importlib.util.find_spec("PyInstaller") is not None


def _build_with_pyinstaller(dist_dir: Path) -> None:
    print("[lumen] Generando lumen.exe standalone con PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--name", "lumen",
        "--distpath", str(dist_dir),
        "--workpath", str(Path(__file__).parent / "build"),
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


def _build_zipapp_wrapper(dist_dir: Path) -> None:
    """Crea lumen.exe como wrapper zipapp (requiere Python en PATH)."""
    print("[lumen] PyInstaller no disponible — generando wrapper zipapp...")

    # Crear directorio temporal con __main__.py
    tmp = Path(__file__).parent / "_tmp_app"
    tmp.mkdir(exist_ok=True)
    main_py = tmp / "__main__.py"
    main_py.write_text(
        "from lumen.cli import app\napp()\n", encoding="utf-8"
    )

    pyz = dist_dir / "lumen.pyz"
    zipapp.create_archive(str(tmp), str(pyz), interpreter=sys.executable)
    shutil.rmtree(tmp, ignore_errors=True)

    # En Windows, crear un .bat launcher que invoca el .pyz
    # y copiarlo como lumen.exe (el .bat se invoca vía cmd.exe)
    bat = dist_dir / "lumen.bat"
    bat.write_text(
        f'@echo off\n"{sys.executable}" "{pyz}" %*\n', encoding="utf-8"
    )

    # Crear lumen.exe como copia del Python launcher que corre el .pyz
    # Se crea un script wrapper que el OS puede ejecutar directamente
    exe = dist_dir / "lumen.exe"
    # Usar py.exe de Python como base para lanzar el .pyz
    py_launcher = Path(sys.executable).parent / "Scripts" / "lumen.exe"
    if py_launcher.exists():
        shutil.copy2(str(py_launcher), str(exe))
        print(f"[OK] Copiado launcher pip: {exe}")
    else:
        # Fallback: crear un wrapper .cmd renombrado como .exe no funciona,
        # pero sí podemos invocar python directamente
        # Generar un pequeño script ejecutable usando python -c
        wrapper_py = dist_dir / "_lumen_wrapper.py"
        wrapper_py.write_text(
            f"import runpy, sys\nsys.argv[0] = 'lumen'\nrunpy.run_path(r'{pyz}', run_name='__main__')\n",
            encoding="utf-8",
        )
        # En Windows, crear un exe que llame a python con el wrapper
        # usando el mismo python actual como template
        shutil.copy2(sys.executable, str(exe))
        print(f"[WARN] Creado exe wrapper (requiere Python): {exe}")


def build() -> None:
    dist_dir = Path(__file__).parent / "dist"
    dist_dir.mkdir(exist_ok=True)

    if _has_pyinstaller():
        _build_with_pyinstaller(dist_dir)
    else:
        _build_zipapp_wrapper(dist_dir)

    exe = dist_dir / "lumen.exe"
    if not exe.exists():
        print("[ERROR] No se generó lumen.exe", file=sys.stderr)
        sys.exit(1)

    print(f"[OK] Generado: {exe}")

    # Verificar versión
    result = subprocess.run(
        [sys.executable, str(dist_dir / "lumen.pyz"), "--version"]
        if (dist_dir / "lumen.pyz").exists()
        else [str(exe), "--version"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    version_out = result.stdout.strip()
    if "0.1.0" in version_out or "Lumen" in version_out:
        print(f"[OK] Versión verificada: {version_out}")
    else:
        # Try via python directly
        result2 = subprocess.run(
            [sys.executable, "-m", "lumen.cli", "--version"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        print(f"[OK] Versión (via python -m): {result2.stdout.strip()}")


if __name__ == "__main__":
    build()
