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


# Lado mínimo (px) al que se escala la imagen antes del OCR. Las fotos de DNI
# suelen venir chicas y el MRZ se lee mucho mejor con más resolución.
_MIN_SIDE = 1000


def _preprocess(img: np.ndarray) -> np.ndarray:
    """
    Mejora la imagen para el OCR del MRZ:
      - escala hacia arriba si es pequeña,
      - convierte a escala de grises,
      - aplica umbralizado adaptativo (resalta texto sobre fondos irregulares).
    """
    h, w = img.shape[:2]
    scale = _MIN_SIDE / min(h, w)
    if scale > 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    # PaddleOCR espera 3 canales.
    return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)


def _ocr_lines(img: np.ndarray) -> List[str]:
    """Ejecuta OCR sobre una imagen ya decodificada y devuelve las líneas."""
    result = get_ocr().ocr(img)
    lines = []
    if result and result[0]:
        for detection in result[0]:
            lines.append(detection[1][0])  # texto extraído
    return lines


def extract_lines_from_image(image_bytes: bytes) -> List[str]:
    """
    Ejecuta OCR sobre la imagen original y sobre una versión preprocesada,
    combinando las líneas. Así, si una de las dos lee mejor el MRZ, el parser
    igual lo encuentra (el parser elige el mejor resultado entre todas).
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return []

    lines = _ocr_lines(img)
    try:
        lines += _ocr_lines(_preprocess(img))
    except cv2.error:
        pass  # si el preprocesamiento falla, nos quedamos con el OCR original
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
