"""
Verifica que el dict que producen los parsers encaja en los modelos Pydantic
de respuesta (evita errores 500 por desajuste de schema al serializar).
"""

from app.models import ProcessResponse
from app.mrz_parser import parse_mrz
from tests.test_mrz_parser import ARG_LINES


def test_parser_output_fits_response_model():
    data = parse_mrz(ARG_LINES)
    assert data is not None
    data["isExpired"] = False

    # No debe lanzar ValidationError.
    response = ProcessResponse(
        sessionId="s1",
        status="approved",
        validations=[],
        data=data,
    )
    assert response.data.name == "Alan Gabriel"
    assert response.data.mrzValid is False
    assert response.status == "approved"
