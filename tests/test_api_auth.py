"""
Tests de autenticación y comportamiento del endpoint.

El OCR se mockea (devuelve líneas MRZ predefinidas) para no depender del modelo
ni de imágenes reales: acá interesa la auth y el flujo del endpoint.
"""

import pytest
from fastapi.testclient import TestClient

from app import main
from tests.test_mrz_parser import ARG_LINES

USER = "admin"
PASSWORD = "changeme"


@pytest.fixture
def client(monkeypatch):
    # Credenciales conocidas para el test (require_auth lee estos globals).
    monkeypatch.setattr("app.security._USERNAME", USER)
    monkeypatch.setattr("app.security._PASSWORD", PASSWORD)
    # Evitamos ejecutar OCR real: cualquier imagen devuelve las líneas del DNI AR.
    monkeypatch.setattr(main, "extract_lines_from_image", lambda _: ARG_LINES)
    return TestClient(main.app)


def _fake_image():
    return {"backImage": ("dorso.jpg", b"fake-bytes", "image/jpeg")}


def test_health_no_requiere_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_process_sin_credenciales_rechaza(client):
    resp = client.post("/api/v1/ocr/process", files=_fake_image())
    assert resp.status_code == 401


def test_process_credenciales_invalidas_rechaza(client):
    resp = client.post("/api/v1/ocr/process", files=_fake_image(), auth=("admin", "wrong"))
    assert resp.status_code == 401


def test_process_credenciales_validas_ok(client):
    resp = client.post("/api/v1/ocr/process", files=_fake_image(), auth=(USER, PASSWORD))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["data"]["lastName"] == "Sanjurjo"
