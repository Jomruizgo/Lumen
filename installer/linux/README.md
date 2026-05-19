# Instalador Linux — Lumen

Genera un binario ELF standalone `lumen` (sin necesitar Python instalado) usando PyInstaller.

## Requisitos previos

- Python 3.11+
- PyInstaller:
  ```bash
  pip install pyinstaller
  ```
  O si usas Poetry:
  ```bash
  poetry install
  ```

## Uso con Make

Desde la **raíz del proyecto**:

```bash
# Compilar el binario
make -f installer/linux/Makefile

# Instalar en /usr/local/bin
sudo make -f installer/linux/Makefile install

# Limpiar artefactos
make -f installer/linux/Makefile clean

# Generar paquete .deb (requiere dpkg-deb)
make -f installer/linux/Makefile deb
```

O entrar al directorio primero:

```bash
cd installer/linux
make all        # compilar
sudo make install   # instalar en /usr/local/bin
make clean      # limpiar
```

Para instalar en un prefijo distinto:

```bash
sudo make install INSTALL_PREFIX=/usr/bin
```

## Uso directo con Python

```bash
python installer/linux/build.py
```

O con el shell script:

```bash
bash installer/linux/build.sh
```

## Archivos generados

| Ruta | Descripción |
|------|-------------|
| `installer/linux/dist/lumen` | Binario ELF standalone |
| `installer/linux/build/` | Archivos intermedios de PyInstaller (descartables) |
| `installer/linux/lumen.spec` | Spec file generado por PyInstaller |

## Verificar el build

```bash
installer/linux/dist/lumen --version
# Lumen 0.1.0
```

## Notas

- El build usa `--onefile` para empaquetar todo en un solo binario portable.
- El binario generado es específico de la arquitectura del host (amd64, arm64, etc.).
- Para builds reproducibles en CI, usa un contenedor Docker con la imagen base correspondiente.
