"""
Capa de OCR sobre PaddleOCR.

El modelo se carga de forma perezosa (en el primer uso real) para que importar
este módulo —por ejemplo en los tests del parser— sea instantáneo.
"""

import io
from typing import List

import cv2
import numpy as np
from paddleocr import PaddleOCR
from pypdf import PdfReader

_ocr = None


def get_ocr() -> PaddleOCR:
    """Devuelve la instancia de PaddleOCR, inicializándola si hace falta."""
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(use_angle_cls=True, lang="es", use_gpu=False)
    return _ocr


def extract_lines_from_image(image_bytes: bytes) -> List[str]:
    """Ejecuta OCR sobre una imagen y devuelve las líneas de texto detectadas."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return []

    result = get_ocr().ocr(img)
    lines = []
    if result and result[0]:
        for detection in result[0]:
            lines.append(detection[1][0])  # texto extraído
    return lines


def extract_lines_from_pdf(pdf_bytes: bytes) -> List[str]:
    """Extrae el texto embebido de un PDF (no hace OCR de PDFs escaneados)."""
    lines: List[str] = []
    reader = PdfReader(io.BytesIO(pdf_bytes))
    for page in reader.pages:
        text = page.extract_text()
        if text:
            lines.extend(text.split("\n"))
    return lines
