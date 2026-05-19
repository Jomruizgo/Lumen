"""Formatter de código Lumen. Formato único, idempotente.

Estrategia: recorre línea a línea preservando la indentación original.
El cuerpo de cada línea se normaliza con cuidado de no tocar contenido
dentro de literales de string (comillas simples o dobles).
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def format_source(source: str) -> str:
    """Formatea código Lumen con reglas canónicas.

    Reglas:
    - Indentación: 2 espacios (tabs → 2 espacios)
    - Espacios alrededor de operadores binarios (=, +, -, *, /, |, ->,
      ==, !=, >=, <=, >, <)
    - Pipelines: ``|`` permanece en la misma línea, con espacios a cada lado
    - Strings usan comillas dobles
    - Máximo 2 líneas en blanco consecutivas
    - Siempre termina con \\n
    - Idempotente: format(format(x)) == format(x)

    Si el source no se puede procesar (no es str), retorna source sin cambios.
    """
    if not isinstance(source, str):
        return source

    lines = source.splitlines()
    result: list[str] = []

    for line in lines:
        line = _normalize_line(line)
        result.append(line)

    formatted = "\n".join(result)
    formatted = _normalize_blank_lines(formatted)

    if not formatted.endswith("\n"):
        formatted += "\n"

    return formatted


def check_format(source: str) -> bool:
    """Retorna True si el source ya está formateado correctamente."""
    return format_source(source) == source


# ---------------------------------------------------------------------------
# Normalización de una línea
# ---------------------------------------------------------------------------

def _normalize_line(line: str) -> str:
    """Normaliza una línea preservando la indentación."""
    # Separar indentación del cuerpo
    body = line.lstrip()
    raw_indent = line[: len(line) - len(body)]

    # Normalizar la indentación: tabs → 2 espacios cada uno
    indent = raw_indent.replace("\t", "  ")

    if not body:
        return ""

    # Si es una línea de comentario, no tocar el cuerpo excepto la indentación
    if body.startswith("#"):
        return indent + body

    # Normalizar el cuerpo respetando los literales de string
    body = _normalize_body(body)

    return indent + body


def _normalize_body(body: str) -> str:
    """Normaliza el cuerpo de una línea (sin la indentación).

    Divide el cuerpo en segmentos: strings y código.
    Solo procesa los segmentos de código.

    Las líneas de continuación de pipeline que empiezan con ``|`` se
    tratan de forma especial para garantizar idempotencia.
    """
    # Línea de continuación de pipeline: "| resto"
    # Aseguramos que el cuerpo sea exactamente "| resto" (sin espacio extra antes)
    if body.startswith("|"):
        rest = body[1:].lstrip()
        rest = _normalize_body_inner(rest)
        return "| " + rest if rest else "|"

    return _normalize_body_inner(body)


def _normalize_body_inner(body: str) -> str:
    """Normaliza el cuerpo de una línea sin tratamiento especial de pipelines."""
    segments = _split_strings(body)
    processed: list[str] = []

    for seg_type, seg_content in segments:
        if seg_type == "code":
            processed.append(_format_code_segment(seg_content))
        else:
            # Segmento de string: normalizar comillas simples → dobles
            # solo si es un literal de comilla simple completo
            processed.append(_normalize_string_literal(seg_content))

    return "".join(processed)


def _normalize_string_literal(s: str) -> str:
    """Convierte un literal de comilla simple a comillas dobles."""
    if s.startswith("'") and s.endswith("'") and len(s) >= 2:
        inner = s[1:-1]
        # Solo convertir si el interior no contiene comillas dobles no escapadas
        if '"' not in inner:
            return '"' + inner + '"'
    return s


# ---------------------------------------------------------------------------
# División en segmentos (string vs código)
# ---------------------------------------------------------------------------

def _split_strings(text: str) -> list[tuple[str, str]]:
    """Divide el texto en segmentos alternando entre código y literales de string.

    Retorna lista de (tipo, contenido) donde tipo es 'code' o 'string'.
    Maneja: strings con comillas dobles, comillas simples e interpolación ${...}.
    Los comentarios (#) se mantienen como código (ya tratados antes).
    """
    segments: list[tuple[str, str]] = []
    i = 0
    code_start = 0

    while i < len(text):
        ch = text[i]

        # Inicio de string con comilla doble
        if ch == '"':
            if i > code_start:
                segments.append(("code", text[code_start:i]))
            end = _find_string_end(text, i, '"')
            segments.append(("string", text[i:end]))
            i = end
            code_start = i
            continue

        # Inicio de string con comilla simple
        if ch == "'":
            if i > code_start:
                segments.append(("code", text[code_start:i]))
            end = _find_string_end(text, i, "'")
            segments.append(("string", text[i:end]))
            i = end
            code_start = i
            continue

        i += 1

    # Resto como código
    if code_start < len(text):
        segments.append(("code", text[code_start:]))

    return segments if segments else [("code", text)]


def _find_string_end(text: str, start: int, quote: str) -> int:
    """Encuentra el índice después del cierre del string.

    Maneja escapes (\\) y strings de interpolación (${...}) dentro
    de strings de comillas dobles.
    """
    i = start + 1  # skip opening quote
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2  # skip escaped character
            continue
        if ch == quote:
            return i + 1
        # Interpolación dentro de string de comillas dobles
        if quote == '"' and ch == "$" and i + 1 < len(text) and text[i + 1] == "{":
            i += 2  # skip ${
            depth = 1
            while i < len(text) and depth > 0:
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                i += 1
            continue
        i += 1
    return len(text)


# ---------------------------------------------------------------------------
# Formateo del segmento de código
# ---------------------------------------------------------------------------

# Tabla de operadores a normalizar (orden importa: más largos primero)
_BINARY_OPS = ["==", "!=", ">=", "<=", "->", ">", "<", "+", "-", "*", "/", "|", "="]


def _format_code_segment(code: str) -> str:
    """Agrega espacios alrededor de operadores en un segmento de código puro.

    Preserva múltiples espacios de indentación al inicio (ya separados).
    Este código no contiene literales de string.
    """
    if not code.strip():
        return code

    result = _add_spaces_around_operators(code)
    # Colapsar múltiples espacios internos pero NO al inicio
    # (la indentación ya fue separada en _normalize_line)
    result = _collapse_internal_spaces(result)
    return result


def _add_spaces_around_operators(code: str) -> str:
    """Agrega espacios alrededor de operadores binarios.

    Usa sustitución cuidadosa para no romper:
    - Signos negativos unarios: -5, -x
    - Comentarios: # ...
    - Accesos a campos: x.y
    - Wildcards y operadores de error: ?, !
    - Tipos parametrizados: Map<Text>
    - Cron strings: "0 8 * * *"
    - Lambdas: e -> e.field
    """
    # Usamos tokenización simple basada en estado para insertar espacios

    # Paso 1: normalizar operadores compuestos (== != >= <= ->)
    # Quitar espacios extra alrededor de ellos primero para re-normalizarlos
    code = re.sub(r"\s*==\s*", " == ", code)
    code = re.sub(r"\s*!=\s*", " != ", code)
    code = re.sub(r"\s*>=\s*", " >= ", code)
    code = re.sub(r"\s*<=\s*", " <= ", code)
    code = re.sub(r"\s*->\s*", " -> ", code)

    # Paso 2: operadores simples (evitando los ya procesados como parte de compuestos)
    # Para | (pipe): espacios alrededor, pero no dentro de < > (tipos genéricos)
    code = re.sub(r"(?<![=!<>])\|(?!=)", " | ", code)
    # Para = (asignación): no tocar ==, !=, <=, >=, ->
    code = re.sub(r"(?<![=!<>-])=(?!=)", " = ", code)
    # Para > y < simples: no tocar ->, >=, <=, ==
    code = re.sub(r"(?<![-=!<])>(?![=>])", " > ", code)
    code = re.sub(r"(?<![=!<])< (?![=<])", " < ", code)  # solo si hay espacio (evitar generics)
    # Para + - * /: cuidado con negativos unarios y strings
    code = re.sub(r"(?<=\w)\+(?=\S)", " + ", code)  # + después de palabra
    code = re.sub(r"(?<=\S)\+(?=\w)", " + ", code)  # + antes de palabra
    code = re.sub(r"(?<=[\w\)])\-(?=[\w\(])", " - ", code)  # - binario
    code = re.sub(r"(?<=\w)\*(?=\S)", " * ", code)
    code = re.sub(r"(?<=\S)\*(?=\w)", " * ", code)
    code = re.sub(r"(?<=\w)\/(?=\S)", " / ", code)
    code = re.sub(r"(?<=\S)\/(?=\w)", " / ", code)

    return code


def _collapse_internal_spaces(code: str) -> str:
    """Colapsa secuencias de más de un espacio en el interior del código.

    No toca los espacios al inicio (indentación ya separada).
    """
    # Solo colapsar espacios en posiciones no iniciales
    # El código ya viene sin indentación al inicio (la indentación fue separada)
    return re.sub(r"  +", " ", code)


# ---------------------------------------------------------------------------
# Normalización de líneas en blanco
# ---------------------------------------------------------------------------

def _normalize_blank_lines(source: str) -> str:
    """Colapsa más de 2 líneas en blanco consecutivas a máximo 2."""
    return re.sub(r"\n{3,}", "\n\n", source)
