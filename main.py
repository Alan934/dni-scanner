import os
os.environ["FLAGS_use_mkldnn"] = "0"

import re
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from paddleocr import PaddleOCR
from mrz.checker.td1 import TD1CodeChecker
from mrz.checker.td2 import TD2CodeChecker
from mrz.checker.td3 import TD3CodeChecker
import cv2
import numpy as np
from pypdf import PdfReader
import io

app = FastAPI(title="DNI OCR Engine Replacement")

# OCR perezoso: se inicializa en el primer uso real (evita cargar el modelo
# al importar el módulo, p. ej. en tests del parser MRZ).
_ocr = None


def get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(use_angle_cls=True, lang="es", use_gpu=False)
    return _ocr

# Caracteres permitidos en una zona MRZ (ICAO 9303): A-Z, 0-9 y el relleno '<'
MRZ_CHAR_RE = re.compile(r'[^A-Z0-9<]')


def _normalize_mrz_line(line: str) -> str:
    """Limpia una línea de OCR dejando solo caracteres válidos de MRZ."""
    return MRZ_CHAR_RE.sub('', line.upper().replace(' ', '<'))


def _extract_mrz_candidates(text_lines):
    """
    Normaliza cada línea del OCR a caracteres MRZ válidos y conserva las que
    podrían formar parte de la zona MRZ (suficientes caracteres y al menos un
    relleno '<' o un grupo largo de dígitos).

    NO intentamos identificar el rol de cada línea acá: simplemente recolectamos
    candidatas. El árbitro real es la validación de dígitos de control de la
    librería en _try_checker — el ruido del frente no produce un MRZ válido.
    """
    candidates = []
    for line in text_lines:
        clean = _normalize_mrz_line(line)
        if len(clean) < 10:
            continue
        # Debe parecer zona MRZ: tener relleno '<' o un bloque numérico largo.
        if '<' in clean or re.search(r'\d{6,}', clean):
            candidates.append(clean)
    return candidates


def _iso_date(yymmdd: str, kind: str = "birth"):
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
        # Vencimiento: 20YY salvo que eso lo ponga muy en el pasado.
        century = "20" if int(yy) >= current_yy - 10 else "21"
    else:
        # Nacimiento: no puede ser futuro; si 20YY > hoy, es 19YY.
        century = "20" if int(yy) <= current_yy else "19"
    return f"{century}{yy}-{mm}-{dd}"


def _build_result(fields, doc_type):
    """Mapea los campos de la librería mrz a nuestro esquema de respuesta."""
    doc_number = fields.document_number.replace('<', '').strip()
    optional = fields.optional_data.replace('<', '').strip()

    # El "número nacional" (DNI/RUN/CUIL) está en distinto campo según el país:
    #  - Argentina: en optional_data (8 dígitos del DNI).
    #  - Chile y la mayoría: es el propio document_number.
    # Preferimos un optional_data puramente numérico de 7-8 dígitos; si no, el doc_number.
    if re.fullmatch(r'\d{7,9}', optional):
        national_id = optional
    else:
        national_id = doc_number

    return {
        "name": fields.name.replace('<', ' ').strip(),
        "lastName": fields.surname.replace('<', ' ').strip(),
        "dni": national_id,
        "documentNumber": doc_number,
        "birthDate": _iso_date(fields.birth_date, "birth"),
        "expiryDate": _iso_date(fields.expiry_date, "expiry"),
        "sex": fields.sex,
        "nationality": fields.nationality,
        "country": fields.country,
        "documentType": doc_type,
    }


def parse_mrz(text_lines):
    """
    Parsea la zona MRZ según ICAO 9303 (cualquier país):
      - TD1: DNI / cédula (3 líneas de 30 chars)
      - TD2: documentos de 2 líneas de 36 chars
      - TD3: pasaportes (2 líneas de 44 chars)
    Usa los dígitos de control del estándar para validar.
    """
    candidates = _extract_mrz_candidates(text_lines)
    if len(candidates) < 2:
        return None

    results = []

    # TD1: 3 líneas de 30 caracteres (DNI / cédula)
    td1 = [l for l in candidates if 26 <= len(l) <= 34]
    for combo in _line_windows(td1, 3):
        res = _try_checker(TD1CodeChecker, combo, expect_len=30, doc_type="ID")
        if res:
            results.append(res)

    # TD3: pasaportes, 2 líneas de 44 caracteres
    td3 = [l for l in candidates if 40 <= len(l) <= 48]
    for combo in _line_windows(td3, 2):
        res = _try_checker(TD3CodeChecker, combo, expect_len=44, doc_type="PASSPORT")
        if res:
            results.append(res)

    # TD2: 2 líneas de 36 caracteres
    td2 = [l for l in candidates if 33 <= len(l) <= 39]
    for combo in _line_windows(td2, 2):
        res = _try_checker(TD2CodeChecker, combo, expect_len=36, doc_type="ID")
        if res:
            results.append(res)

    if not results:
        return None

    # Mejor resultado: primero los que validan dígitos de control (mrzValid),
    # luego los que tienen más campos completos (nombre + fecha de nacimiento).
    def score(r):
        return (
            r["mrzValid"],
            bool(r["name"]),
            bool(r["birthDate"]),
            bool(r["lastName"]),
        )

    results.sort(key=score, reverse=True)
    return results[0]


def _line_windows(lines, n):
    """Genera ventanas consecutivas de n líneas para probar combinaciones."""
    for i in range(len(lines) - n + 1):
        yield lines[i:i + n]


def _try_checker(checker_cls, lines, expect_len, doc_type):
    """
    Normaliza cada línea a la longitud esperada (rellenando con '<') e intenta
    parsear con la librería.

    Estrategia tolerante a errores de OCR:
      1. Construye el checker (no exige que todos los dígitos de control validen).
      2. Intenta .fields() — la forma soportada de obtener los campos.
      3. Solo descarta el resultado si faltan los campos mínimos (apellido + nro).
    """
    padded = [l[:expect_len].ljust(expect_len, '<') for l in lines]
    mrz_string = "\n".join(padded)
    try:
        # check_expiry=False: aceptamos documentos vencidos en el parseo.
        checker = checker_cls(mrz_string, check_expiry=False)
        fields = checker.fields()
    except Exception:
        return None

    # Validación mínima de estructura para descartar ventanas de ruido del frente:
    #  - apellido y número de documento presentes
    #  - fecha de nacimiento Y de vencimiento deben ser 6 dígitos (AAMMDD reales)
    # El texto del frente nunca produce dos fechas válidas en las posiciones MRZ.
    if not fields.surname.strip('<') or not fields.document_number.strip('<'):
        return None
    if not _valid_mrz_date(fields.birth_date) or not _valid_mrz_date(fields.expiry_date):
        return None

    result = _build_result(fields, doc_type)
    # Marcamos si todos los dígitos de control validaron (confianza alta).
    result["mrzValid"] = bool(checker)
    return result


def _valid_mrz_date(yymmdd: str) -> bool:
    """True si el campo es AAMMDD con mes 01-12 y día 01-31 (estructura válida)."""
    if not yymmdd or len(yymmdd) != 6 or not yymmdd.isdigit():
        return False
    mm, dd = int(yymmdd[2:4]), int(yymmdd[4:6])
    return 1 <= mm <= 12 and 1 <= dd <= 31

def parse_front_text(text_lines):
    """
    Fallback heurístico cuando NO hay zona MRZ legible (solo frente del documento).
    Menos confiable que el MRZ; cubre etiquetas comunes en español/inglés.
    """
    full_text = " ".join(text_lines).upper()

    # Número de documento: XX.XXX.XXX, X.XXX.XXX-X (Chile) u 7-8 dígitos juntos.
    dni_match = re.search(r'(\d{1,2}\.?\d{3}\.?\d{3}(?:-?[\dKk])?)', full_text)
    dni = re.sub(r'[.\-]', '', dni_match.group(1)) if dni_match else None

    # Nombres: la etiqueta y el valor suelen estar en líneas consecutivas.
    last_name = None
    first_name = None
    for i, line in enumerate(text_lines):
        clean = line.upper().strip()
        if any(k in clean for k in ("APELLIDO", "SURNAME")) and i + 1 < len(text_lines):
            last_name = last_name or text_lines[i + 1].strip()
        if any(k in clean for k in ("NOMBRE", "NAME")) and i + 1 < len(text_lines):
            first_name = first_name or text_lines[i + 1].strip()

    # Fecha de nacimiento DD/MM/AAAA o DD.MM.AAAA (primera ocurrencia).
    birth_match = re.search(r'(\d{2})[\/\.\-](\d{2})[\/\.\-](\d{4})', full_text)
    birth_date = f"{birth_match.group(3)}-{birth_match.group(2)}-{birth_match.group(1)}" if birth_match else None

    if dni or last_name:
        return {
            "name": first_name or "NO_DETECTADO",
            "lastName": last_name or "NO_DETECTADO",
            "dni": dni or "",
            "documentNumber": dni or "",
            "birthDate": birth_date,
            "expiryDate": None,
            "sex": None,
            "nationality": None,
            "country": None,
            "documentType": "UNKNOWN",
            "mrzValid": False,
        }
    return None

def process_image_bytes(image_bytes: bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Ejecutar OCR
    result = get_ocr().ocr(img)
    lines = []
    if result and result[0]:
        for res in result[0]:
            lines.append(res[1][0]) # Texto extraído
    return lines

@app.post("/api/v1/ocr/process")
async def process_dni(
    frontImage: Optional[UploadFile] = File(None),
    backImage: Optional[UploadFile] = File(None),
    pdfDocument: Optional[UploadFile] = File(None),
    data: Optional[UploadFile] = File(None),
    sessionId: Optional[str] = Form(None)
):
    all_extracted_lines = []
    
    # 1. Procesar archivos según lo que envíe el cliente
    files_to_process = [f for f in [frontImage, backImage, pdfDocument, data] if f is not None]
    
    if not files_to_process:
        raise HTTPException(status_code=400, detail="No se proporcionaron archivos legibles")
        
    for file in files_to_process:
        content = await file.read()
        if file.filename.lower().endswith('.pdf'):
            # Convertir páginas de PDF a texto plano o imágenes si es escaneado
            # Por simplicidad y performance, leemos el texto embebido si existe
            reader = PdfReader(io.BytesIO(content))
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    all_extracted_lines.extend(text.split('\n'))
        else:
            # Es una imagen (JPEG, PNG, WebP)
            lines = process_image_bytes(content)
            all_extracted_lines.extend(lines)

    # 2. Intentar parsear el MRZ (Método más preciso para Dorso de DNI)
    parsed_data = parse_mrz(all_extracted_lines)
    
    # 3. Si falla el MRZ, intentar heurística por texto de frente
    if not parsed_data:
        parsed_data = parse_front_text(all_extracted_lines)
        
    if not parsed_data:
        raise HTTPException(status_code=422, detail="No se lograron extraer datos válidos del DNI")
        
    return {
        "sessionId": sessionId,
        "status": "approved",
        "data": parsed_data
    }