"""Tests de las validaciones de negocio (vencimiento, coherencia)."""

from app.validators import validate_document


def _base_data(**overrides) -> dict:
    data = {
        "birthDate": "2001-11-07",
        "expiryDate": "2032-01-04",
        "mrzValid": True,
    }
    data.update(overrides)
    return data


def test_documento_vigente():
    approved, is_expired, validations = validate_document(_base_data())
    assert approved is True
    assert is_expired is False
    assert validations == []


def test_documento_vencido():
    approved, is_expired, validations = validate_document(_base_data(expiryDate="2010-01-01"))
    assert approved is True  # se aprueba igual, pero marcado
    assert is_expired is True
    assert any("vencido" in v.lower() for v in validations)


def test_sin_fecha_vencimiento():
    approved, is_expired, validations = validate_document(_base_data(expiryDate=None))
    assert is_expired is False
    assert any("vencimiento" in v.lower() for v in validations)


def test_mrz_no_valido_genera_advertencia():
    _, _, validations = validate_document(_base_data(mrzValid=False))
    assert any("mrz" in v.lower() for v in validations)
