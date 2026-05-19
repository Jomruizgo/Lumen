# Instalador Windows — Lumen

Genera `lumen.exe` standalone (sin necesitar Python instalado) usando PyInstaller.

## Requisitos previos

- Python 3.11+
- PyInstaller (incluido en las dependencias dev del proyecto):
  ```
  pip install pyinstaller
  ```
  O si usas Poetry:
  ```
  poetry install
  ```

## Cómo compilar

Desde el directorio `installer/windows/`:

```cmd
cd installer\windows
python build.py
```

El ejecutable se genera en `installer/windows/dist/lumen.exe`.

## Verificar el build

```cmd
installer\windows\dist\lumen.exe --version
```

Debe imprimir algo como `Lumen 0.1.0`.

## Archivos generados

| Ruta | Descripción |
|------|-------------|
| `installer/windows/dist/lumen.exe` | Ejecutable standalone |
| `installer/windows/build/` | Archivos intermedios de PyInstaller (descartables) |
| `installer/windows/lumen.spec` | Spec file generado por PyInstaller |

## Distribuir

Comparte únicamente `dist/lumen.exe` — es autónomo, no requiere Python ni dependencias adicionales en el equipo destino.

## Notas

- El build usa `--onefile` para empaquetar todo en un solo `.exe`.
- Si el antivirus bloquea el `.exe`, puede ser necesario añadirlo como excepción (falso positivo común con PyInstaller).
- Para builds reproducibles, fija la versión de PyInstaller en `pyproject.toml`.
