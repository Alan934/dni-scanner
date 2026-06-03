"""
Parseo de la zona MRZ (Machine Readable Zone) según el estándar ICAO 9303.

Soporta los tres formatos estándar, por lo que funciona con documentos de
cualquier país sin lógica específica:
    - TD1: DNI / cédula de identidad (3 líneas de 30 caracteres)
    - TD2: documentos de 2 líneas de 36 caracteres
    - TD3: pasaportes (2 líneas de 44 caracteres)

El árbitro de qué líneas forman el MRZ son los dígitos de control del propio
estándar (validados por la librería `mrz`): el texto del frente del documento
no produce un MRZ estructuralmente válido.
"""

import re
from datetime import datetime
from typing import List, Optional

from mrz.checker.td1 import TD1CodeChecker
from mrz.checker.td2 import TD2CodeChecker
from mrz.checker.td3 import TD3CodeChecker

from app.formatting import capitalize_name

# Caracteres permitidos en una zona MRZ (ICAO 9303): A-Z, 0-9 y el relleno '<'.
_MRZ_CHAR_RE = re.compile(r"[^A-Z0-9<]")


def parse_mrz(text_lines: List[str]) -> Optional[dict]:
    """
    Parsea la zona MRZ a partir de las líneas de texto del OCR.
    Devuelve un dict con los datos del documento, o None si no se encontró MRZ.
    """
    candidates = _extract_mrz_candidates(text_lines)
    if len(candidates) < 2:
        return None

    results = []

    # TD1: 3 líneas de 30 caracteres (DNI / cédula).
    td1 = [l for l in candidates if 26 <= len(l) <= 34]
    for combo in _line_windows(td1, 3):
        res = _try_checker(TD1CodeChecker, combo, expect_len=30, doc_type="ID")
        if res:
            results.append(res)

    # TD3: pasaportes, 2 líneas de 44 caracteres.
    td3 = [l for l in candidates if 40 <= len(l) <= 48]
    for combo in _line_windows(td3, 2):
        res = _try_checker(TD3CodeChecker, combo, expect_len=44, doc_type="PASSPORT")
        if res:
            results.append(res)

    # TD2: 2 líneas de 36 caracteres.
    td2 = [l for l in candidates if 33 <= len(l) <= 39]
    for combo in _line_windows(td2, 2):
        res = _try_checker(TD2CodeChecker, combo, expect_len=36, doc_type="ID")
        if res:
            results.append(res)

    if not results:
        return None

    # Mejor resultado: primero los que validan dígitos de control (mrzValid),
    # luego los que tienen más campos completos.
    results.sort(key=_score, reverse=True)
    return results[0]


def _score(result: dict) -> tuple:
    """Prioriza resultados validados y con más campos completos."""
    return (
        result["mrzValid"],
        bool(result["name"]),
        bool(result["birthDate"]),
        bool(result["lastName"]),
    )


def _normalize_mrz_line(line: str) -> str:
    """Limpia una línea de OCR dejando solo caracteres válidos de MRZ."""
    return _MRZ_CHAR_RE.sub("", line.upper().replace(" ", "<"))


def _extract_mrz_candidates(text_lines: List[str]) -> List[str]:
    """
    Normaliza cada línea del OCR a caracteres MRZ y conserva las que podrían
    formar parte de la zona MRZ (suficiente largo y con relleno '<' o un bloque
    numérico largo). No identifica el rol de cada línea: solo recolecta.
    """
    candidates = []
    for line in text_lines:
        clean = _normalize_mrz_line(line)
        if len(clean) < 10:
            continue
        if "<" in clean or re.search(r"\d{6,}", clean):
            candidates.append(clean)
    return candidates


def _line_windows(lines: List[str], n: int):
    """Genera ventanas consecutivas de n líneas para probar combinaciones."""
    for i in range(len(lines) - n + 1):
        yield lines[i:i + n]


def _try_checker(checker_cls, lines, expect_len: int, doc_type: str) -> Optional[dict]:
    """
    Normaliza cada línea a la longitud esperada (rellenando con '<') e intenta
    parsear con la librería. Tolerante a errores menores de OCR: no exige que
    todos los dígitos de control validen, pero sí que la estructura sea coherente.
    """
    padded = [l[:expect_len].ljust(expect_len, "<") for l in lines]
    mrz_string = "\n".join(padded)
    try:
        # check_expiry=False: el parseo acepta documentos vencidos; la validación
        # de vencimiento se hace después, contra la fecha local.
        checker = checker_cls(mrz_string, check_expiry=False)
        fields = checker.fields()
    except Exception:
        return None

    # Validación de estructura para descartar ventanas de ruido del frente:
    # apellido + número de documento presentes y dos fechas MRZ reales.
    if not fields.surname.strip("<") or not fields.document_number.strip("<"):
        return None
    if not _valid_mrz_date(fields.birth_date) or not _valid_mrz_date(fields.expiry_date):
        return None

    result = _build_result(fields, doc_type)
    result["mrzValid"] = bool(checker)
    return result


def _build_result(fields, doc_type: str) -> dict:
    """Mapea los campos de la librería `mrz` al esquema de respuesta."""
    doc_number = fields.document_number.replace("<", "").strip()
    optional = fields.optional_data.replace("<", "").strip()

    # El "número nacional" (DNI/RUN/CUIL) está en distinto campo según el país:
    #  - Argentina: en optional_data (8 dígitos del DNI).
    #  - Chile y la mayoría: es el propio document_number.
    if re.fullmatch(r"\d{7,9}", optional):
        national_id = optional
    else:
        national_id = doc_number

    return {
        "name": capitalize_name(fields.name.replace("<", " ").strip()),
        "lastName": capitalize_name(fields.surname.replace("<", " ").strip()),
        "dni": national_id,
        "documentNumber": doc_number,
        "birthDate": _iso_date(fields.birth_date, "birth"),
        "expiryDate": _iso_date(fields.expiry_date, "expiry"),
        "sex": fields.sex,
        "nationality": fields.nationality,
        "country": fields.country,
        "documentType": doc_type,
    }


def _valid_mrz_date(yymmdd: str) -> bool:
    """True si el campo es AAMMDD con mes 01-12 y día 01-31 (estructura válida)."""
    if not yymmdd or len(yymmdd) != 6 or not yymmdd.isdigit():
        return False
    mm, dd = int(yymmdd[2:4]), int(yymmdd[4:6])
    return 1 <= mm <= 12 and 1 <= dd <= 31


def _iso_date(yymmdd: str, kind: str = "birth") -> Optional[str]:
    """
    Convierte AAMMDD del MRZ a YYYY-MM-DD infiriendo el siglo.
      kind="birth"  -> la fecha está en el pasado (nacimiento).
      kind="expiry" -> la fecha suele ser futura (vencimiento).
    """
    if not yymmdd or len(yymmdd) != 6 or not yymmdd.isdigit():
        return None
    yy, mm, dd = yymmdd[0:2], yymmdd[2:4], yymmdd[4:6]
    current_yy = datetime.now().year % 100
    if kind == "expiry":
        century = "20" if int(yy) >= current_yy - 10 else "21"
    else:
        century = "20" if int(yy) <= current_yy else "19"
    return f"{century}{yy}-{mm}-{dd}"
