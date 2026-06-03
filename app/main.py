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

from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile

from app import __version__
from app.front_parser import parse_front_text
from app.models import ProcessResponse
from app.mrz_parser import parse_mrz
from app.ocr import extract_lines_from_image, extract_lines_from_pdf
from app.security import require_auth
from app.validators import validate_document

app = FastAPI(
    title="DNI Scanner API",
    description="Extracción de datos de documentos de identidad mediante OCR + MRZ (ICAO 9303).",
    version=__version__,
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Healthcheck simple para orquestadores/monitoreo."""
    return {"status": "ok", "version": __version__}


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
    files = [f for f in (frontImage, backImage, pdfDocument, data) if f is not None]
    if not files:
        raise HTTPException(status_code=400, detail="No se proporcionaron archivos legibles")

    all_lines = await _extract_all_lines(files)

    # MRZ primero (más preciso y multinacional); si falla, fallback al frente.
    parsed = parse_mrz(all_lines) or parse_front_text(all_lines)
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


async def _extract_all_lines(files: List[UploadFile]) -> List[str]:
    """Lee todos los archivos y devuelve las líneas de texto combinadas."""
    all_lines: List[str] = []
    for file in files:
        content = await file.read()
        if (file.filename or "").lower().endswith(".pdf"):
            all_lines.extend(extract_lines_from_pdf(content))
        else:
            all_lines.extend(extract_lines_from_image(content))
    return all_lines
