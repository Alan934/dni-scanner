import os
os.environ["FLAGS_use_mkldnn"] = "0"

import re
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from paddleocr import PaddleOCR
import cv2
import numpy as np
from pypdf import PdfReader
import io

app = FastAPI(title="DNI OCR Engine Replacement")

ocr = PaddleOCR(use_angle_cls=True, lang="es", use_gpu=False)

def parse_mrz(text_lines):
    """
    Parsea las líneas del bloque MRZ (dorso del DNI Argentino).
    Formato típico de 3 líneas o 2 líneas estándar OACI.
    """
    mrz_lines = []
    for line in text_lines:
        clean_line = re.sub(r'\s+', '', line).upper()
        # Buscar patrones que contengan los caracteres de relleno '<'
        if '<' in clean_line and (len(clean_line) >= 25 or 'ARG' in clean_line):
            mrz_lines.append(clean_line)
            
    if len(mrz_lines) >= 2:
        try:
            # Lógica para DNI Argentino moderno (formato de 3 líneas de 30 caracteres)
            if len(mrz_lines) == 3 or len(mrz_lines[0]) <= 36:
                # Línea 1: IDARG<NRO_TRÁMITE><<<<<<<<
                # Línea 2: <FECHA_NACIMIENTO><SEXO><FECHA_EXPIRACION><NACIONALIDAD>
                # Línea 3: APELLIDO<<NOMBRE<SEGUNDO_NOMBRE
                
                # Buscamos la línea que tiene los nombres (suele ser la última o tener dobles <<)
                name_line = next((l for l in mrz_lines if '<<' in l), mrz_lines[-1])
                data_line = next((l for l in mrz_lines if any(c.isdigit() for c in l) and 'ARG' in l or (len(l) > 0 and l[0].isdigit())), mrz_lines[1])
                doc_line = next((l for l in mrz_lines if l.startswith('IDARG') or l.startswith('I<ARG')), mrz_lines[0])
                
                # Extraer DNI de la línea de documento o de datos
                dni_match = re.search(r'(?:ARG)?(\d{8})', doc_line + data_line)
                dni = dni_match.group(1) if dni_match else ""
                
                # Extraer Apellidos y Nombres
                name_parts = name_line.replace('I<ARG', '').split('<<')
                last_name = name_parts[0].replace('<', ' ').strip()
                first_name = name_parts[1].replace('<', ' ').strip() if len(name_parts) > 1 else ""
                
                # Fecha de Nacimiento (AAMMDD) -> Convertir a YYYY-MM-DD
                birth_match = re.search(r'(\d{6})', data_line)
                birth_date = None
                if birth_match:
                    raw_date = birth_match.group(1)
                    year_prefix = "19" if int(raw_date[0:2]) > 40 else "20"
                    birth_date = f"{year_prefix}{raw_date[0:2]}-{raw_date[2:4]}-{raw_date[4:6]}"
                
                return {
                    "name": first_name,
                    "lastName": last_name,
                    "dni": dni,
                    "birthDate": birth_date,
                    "documentType": "DNI"
                }
        except Exception:
            pass
    return None

def parse_front_text(text_lines):
    """
    Fallback heurístico si solo se procesa el frente del DNI.
    """
    full_text = " ".join(text_lines).upper()
    
    # Extraer DNI (Formato XX.XXX.XXX u 8 dígitos juntos)
    dni_match = re.search(r'(\d{2}\.?\d{3}\.?\d{3})', full_text)
    dni = dni_match.group(1).replace('.', '') if dni_match else None
    
    # Heurística básica de nombres basada en líneas comunes del frente del DNI argentino
    last_name = None
    first_name = None
    
    for i, line in enumerate(text_lines):
        clean_line = line.upper().strip()
        if "APELLIDO" in clean_line and i + 1 < len(text_lines):
            last_name = text_lines[i+1].strip()
        if "NOMBRE" in clean_line and i + 1 < len(text_lines):
            first_name = text_lines[i+1].strip()
            
    # Intentar parsear fecha de nacimiento DD/MM/AAAA o DD.MM.AAAA
    birth_match = re.search(r'(\d{2})[\/\.](\d{2})[\/\.](\d{4})', full_text)
    birth_date = f"{birth_match.group(3)}-{birth_match.group(2)}-{birth_match.group(1)}" if birth_match else None

    if dni or last_name:
        return {
            "name": first_name or "NO_DETECTADO",
            "lastName": last_name or "NO_DETECTADO",
            "dni": dni or "",
            "birthDate": birth_date,
            "documentType": "DNI"
        }
    return None

def process_image_bytes(image_bytes: bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Ejecutar OCR
    result = ocr.ocr(img)
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