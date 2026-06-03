"""
Parseo heurístico del FRENTE del documento.

Se usa solo como fallback cuando no hay una zona MRZ legible (por ejemplo, si el
cliente envió únicamente el frente). Es bastante menos confiable que el MRZ y
cubre las etiquetas más comunes en español/inglés.
"""

import re
from typing import List, Optional

from app.formatting import capitalize_name

_LASTNAME_LABELS = ("APELLIDO", "SURNAME")
_NAME_LABELS = ("NOMBRE", "NAME")


def parse_front_text(text_lines: List[str]) -> Optional[dict]:
    """Extrae datos del frente del documento. Devuelve dict o None."""
    full_text = " ".join(text_lines).upper()

    # Número de documento: XX.XXX.XXX, X.XXX.XXX-X (Chile) u 7-8 dígitos juntos.
    dni_match = re.search(r"(\d{1,2}\.?\d{3}\.?\d{3}(?:-?[\dKk])?)", full_text)
    dni = re.sub(r"[.\-]", "", dni_match.group(1)) if dni_match else None

    # Nombres: la etiqueta y el valor suelen estar en líneas consecutivas.
    last_name = None
    first_name = None
    for i, line in enumerate(text_lines):
        clean = line.upper().strip()
        if any(k in clean for k in _LASTNAME_LABELS) and i + 1 < len(text_lines):
            last_name = last_name or text_lines[i + 1].strip()
        if any(k in clean for k in _NAME_LABELS) and i + 1 < len(text_lines):
            first_name = first_name or text_lines[i + 1].strip()

    # Fecha de nacimiento DD/MM/AAAA o DD.MM.AAAA (primera ocurrencia).
    birth_match = re.search(r"(\d{2})[\/\.\-](\d{2})[\/\.\-](\d{4})", full_text)
    birth_date = (
        f"{birth_match.group(3)}-{birth_match.group(2)}-{birth_match.group(1)}"
        if birth_match
        else None
    )

    if not (dni or last_name):
        return None

    return {
        "name": capitalize_name(first_name) if first_name else "NO_DETECTADO",
        "lastName": capitalize_name(last_name) if last_name else "NO_DETECTADO",
        "dni": dni or "",
        "documentNumber": dni or "",
        "birthDate": birth_date,
        "expiryDate": None,
        "sex": None,
        "nationality": None,
        "country": None,
        "documentType": "UNKNOWN",
        "mrzValid": False,
    }
