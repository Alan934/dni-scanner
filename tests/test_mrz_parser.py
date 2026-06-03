"""
Tests del parser MRZ. Simulan la salida del OCR (lista de líneas de texto)
para documentos reales y verifican la extracción de datos.
"""

from app.mrz_parser import parse_mrz

# DNI argentino (dorso) + ruido del frente que NO debe confundir al parser.
ARG_LINES = [
    "REPUBLICA ARGENTINA - MERCOSUR",
    "REGISTRO NACIONAL DE LAS PERSONAS",
    "Apellido / Surname",
    "SANJURJO",
    "Nombre / Name",
    "ALAN GABRIEL",
    "Fecha de nacimiento / Date of birth",
    "Lic. D. Rogelio Frigerio",
    "Ministro del Interior O. Pub. y Vivienda",
    "IDARG42584758<0<<<<<<<<<<<<<<<<",
    "0111078M3201048ARG<<<<<<<<<<<<2",
    "SANJURJO<<ALAN<GABRIEL<<<<<<<<<",
]

# Cédula chilena (dorso).
CHL_LINES = [
    "Nacio en: Santiago",
    "Profesion: ASISTENTE SOCIAL",
    "INCHLBA30111850A01<<<<<<<<<<<<<",
    "9903078M3003079CHL80000013<0<3",
    "FREDEZ<MATURANA<<JOAQUIN<LEON<<",
]


def test_dni_argentino():
    result = parse_mrz(ARG_LINES)
    assert result is not None
    assert result["name"] == "Alan Gabriel"
    assert result["lastName"] == "Sanjurjo"
    assert result["dni"] == "42584758"
    assert result["birthDate"] == "2001-11-07"
    assert result["expiryDate"] == "2032-01-04"
    assert result["sex"] == "M"
    assert result["nationality"] == "ARG"


def test_cedula_chilena():
    result = parse_mrz(CHL_LINES)
    assert result is not None
    assert result["name"] == "Joaquin Leon"
    assert result["lastName"] == "Fredez Maturana"
    assert result["birthDate"] == "1999-03-07"
    assert result["expiryDate"] == "2030-03-07"
    assert result["sex"] == "M"
    assert result["nationality"] == "CHL"
    assert result["mrzValid"] is True


def test_sin_mrz_devuelve_none():
    # Solo texto del frente, sin zona MRZ.
    assert parse_mrz(["REPUBLICA ARGENTINA", "Nombre: Juan"]) is None
