"""
API FastAPI para extracción de datos de documentos de identidad.

Flujo:
    1. Recibe imágenes (frente/dorso) o un PDF.
    2. Ejecuta OCR sobre las imágenes (PaddleOCR).
    3. Parsea la zona MRZ (ICAO 9303) — método principal, multinacional.
    4. Si no hay MRZ, cae a un parseo heurístico del frente.
    5. Valida vencimiento y coherencia contra la fecha local (Mendoza, AR).
"""

# Debe ir antes de importar paddle: desactiva OneDNN para evitar un crash en CPU.
import os

os.environ["FLAGS_use_mkldnn"] = "0"

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile

from app import __version__
from app.front_parser import parse_front_text
from app.models import ProcessResponse
from app.mrz_parser import parse_mrz
from app.ocr import (
    extract_lines_fast,
    extract_lines_from_pdf,
    extract_lines_preprocessed,
    get_ocr,
)
from app.security import require_auth
from app.validators import validate_document

# Indica si el modelo de OCR ya quedó cargado en memoria.
_model_ready = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Precarga el modelo de OCR al arrancar (los pesos ya vienen en la imagen).
    Así el primer request no paga la latencia de carga. Si fallara, la app
    igual arranca: /health sigue respondiendo y el modelo se cargará al usarlo.
    """
    global _model_ready
    try:
        get_ocr()
        _model_ready = True
    except Exception:
        _model_ready = False
    yield


app = FastAPI(
    title="DNI Scanner API",
    description="Extracción de datos de documentos de identidad mediante OCR + MRZ (ICAO 9303).",
    version=__version__,
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """
    Liveness: responde siempre rápido y NO depende del modelo de OCR.
    Lo usa el orquestador para saber que el proceso está vivo. Que devuelva 200
    no implica que el modelo ya esté listo (para eso está /ready).
    """
    return {"status": "ok", "version": __version__}


@app.get("/ready", tags=["meta"])
def ready() -> dict:
    """Readiness: indica si el modelo de OCR ya está cargado y puede procesar."""
    return {"status": "ready" if _model_ready else "loading", "modelReady": _model_ready}


@app.post("/api/v1/ocr/process", response_model=ProcessResponse, tags=["ocr"])
async def process_dni(
    frontImage: Optional[UploadFile] = File(None),
    backImage: Optional[UploadFile] = File(None),
    pdfDocument: Optional[UploadFile] = File(None),
    data: Optional[UploadFile] = File(None),
    sessionId: Optional[str] = Form(None),
    _user: str = Depends(require_auth),
) -> ProcessResponse:
    """Procesa un documento de identidad y devuelve los datos extraídos y validados."""
    if not any((frontImage, backImage, pdfDocument, data)):
        raise HTTPException(status_code=400, detail="No se proporcionaron archivos legibles")

    parsed = await _extract_document_data(frontImage, backImage, pdfDocument, data)
    if not parsed:
        raise HTTPException(status_code=422, detail="No se lograron extraer datos válidos del documento")

    approved, is_expired, validations = validate_document(parsed)
    parsed["isExpired"] = is_expired

    return ProcessResponse(
        sessionId=sessionId,
        status="approved" if approved else "rejected",
        validations=validations,
        data=parsed,
    )


async def _extract_document_data(
    front: Optional[UploadFile],
    back: Optional[UploadFile],
    pdf: Optional[UploadFile],
    extra: Optional[UploadFile],
) -> Optional[dict]:
    """
    Estrategia escalonada "rápido primero": hace solo el OCR necesario y se detiene
    apenas obtiene un MRZ válido. Así el caso normal (DNI legible) responde rápido,
    sin perder robustez ante fotos degradadas.

    Orden de intentos:
      1. PDF: texto embebido (instantáneo).
      2. OCR rápido del dorso (donde está el MRZ).
      3. OCR rápido del resto de imágenes.
      4. Rescate: OCR preprocesado de todas las imágenes.
      5. Fallback heurístico al texto del frente.
    """
    # Imágenes en orden de prioridad: el dorso suele tener el MRZ.
    image_files = [f for f in (back, front, extra) if f is not None]
    image_bytes = [await f.read() for f in image_files]

    accumulated: List[str] = []

    # 1. PDF (texto embebido): rápido y suele traer el MRZ.
    if pdf is not None:
        accumulated += extract_lines_from_pdf(await pdf.read())
        found = parse_mrz(accumulated)
        if found:
            return found

    # 2 y 3. OCR rápido, imagen por imagen, deteniéndonos apenas el MRZ valide.
    for img in image_bytes:
        accumulated += extract_lines_fast(img)
        found = parse_mrz(accumulated)
        if found:
            return found

    # 4. Rescate: OCR preprocesado (más lento) solo si lo rápido no alcanzó.
    for img in image_bytes:
        accumulated += extract_lines_preprocessed(img)
        found = parse_mrz(accumulated)
        if found:
            return found

    # 5. Último recurso: heurística sobre el texto del frente.
    return parse_front_text(accumulated)
