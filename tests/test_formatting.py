"""Tests de capitalización de nombres."""

import pytest

from app.formatting import capitalize_name


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("ALAN GABRIEL", "Alan Gabriel"),
        ("FREDEZ MATURANA", "Fredez Maturana"),
        ("JOAQUIN LEON", "Joaquin Leon"),
        ("DE LA TORRE", "De la Torre"),       # 1ra palabra siempre en mayúscula
        ("MARIA DEL CARMEN", "Maria del Carmen"),  # partículas internas en minúscula
        ("ANA-MARIA", "Ana-Maria"),
        ("", ""),
    ],
)
def test_capitalize_name(raw, expected):
    assert capitalize_name(raw) == expected
