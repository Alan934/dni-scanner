# DNI Scanner API

API REST para la extracción y validación de datos de documentos de identidad
(DNI, cédulas, pasaportes) mediante **OCR** y parseo de la zona **MRZ** según el
estándar internacional **ICAO 9303**.

Al basarse en el MRZ (Machine Readable Zone), funciona con documentos de
**cualquier país** —no solo Argentina— y valida la lectura mediante los dígitos
de control del propio estándar.

---

## Características

- 🌎 **Multinacional**: parsea MRZ en formatos TD1 (DNI/cédula), TD2 y TD3 (pasaportes).
- ✅ **Validación por dígitos de control** ICAO 9303 (campo `mrzValid`).
- 📅 **Validación de vencimiento** contra la fecha local de Mendoza, Argentina.
- 🔤 **Formateo de nombres** a formato Título (`ALAN` → `Alan`).
- 🖼️ Acepta **imágenes** (JPG, PNG, WebP) y **PDF** con texto embebido.
- 🔁 **Fallback** heurístico al frente del documento si no hay MRZ legible.
- 🐳 Listo para correr con **Docker**.

---

## Tecnologías

| Componente | Uso |
|------------|-----|
| [FastAPI](https://fastapi.tiangolo.com/) | Framework web |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | Reconocimiento óptico de caracteres |
| [mrz](https://pypi.org/project/mrz/) | Parseo y validación ICAO 9303 |
| [OpenCV](https://opencv.org/) | Decodificación de imágenes |
| [pypdf](https://pypi.org/project/pypdf/) | Lectura de PDFs |

---

## Estructura del proyecto

```
DNI-scanner/
├── app/
│   ├── main.py          # Endpoints FastAPI y orquestación
│   ├── ocr.py           # Capa de OCR (PaddleOCR) y lectura de PDF
│   ├── mrz_parser.py    # Parseo de la zona MRZ (ICAO 9303)
│   ├── front_parser.py  # Fallback heurístico del frente
│   ├── validators.py    # Validaciones de negocio (vencimiento, etc.)
│   ├── formatting.py    # Capitalización de nombres
│   └── models.py        # Schemas Pydantic de la respuesta
├── tests/               # Tests con pytest
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Puesta en marcha

### Requisitos

- [Docker](https://www.docker.com/) y Docker Compose.

### Configuración

El endpoint de procesamiento está protegido con **HTTP Basic**. Copiá
`.env.example` a `.env` y definí las credenciales:

```bash
cp .env.example .env
```

```env
API_USERNAME=admin
API_PASSWORD=una-clave-segura
```

> ⚠️ Si `API_PASSWORD` no está definida, la API rechaza todas las peticiones al
> endpoint protegido (falla cerrada). El archivo `.env` **no** se sube al repo.

### Levantar el servicio

```bash
docker compose up --build
```

La API queda disponible en **http://localhost:8000**.

- Documentación interactiva (Swagger): **http://localhost:8000/docs**
- Healthcheck: **http://localhost:8000/health**

> El primer arranque descarga los modelos de PaddleOCR (~unos minutos). Quedan
> cacheados en un volumen, por lo que los siguientes arranques son rápidos.

### Desarrollo (hot-reload)

El `docker-compose.yml` monta la carpeta `app/` como volumen con `--reload`
activado: al guardar cambios en el código, el servidor se reinicia solo, sin
necesidad de reconstruir la imagen.

Solo es necesario reconstruir (`docker compose build`) cuando cambian
`requirements.txt` o el `Dockerfile`.

---

## Uso de la API

### `POST /api/v1/ocr/process` 🔒

Procesa un documento y devuelve los datos extraídos. **Requiere autenticación
HTTP Basic** (usuario y contraseña configurados por variables de entorno).

**Parámetros** (multipart/form-data), todos opcionales pero al menos uno requerido:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `frontImage` | archivo | Imagen del frente del documento |
| `backImage` | archivo | Imagen del dorso (contiene el MRZ) |
| `pdfDocument` | archivo | PDF del documento |
| `data` | archivo | Archivo genérico (imagen) |
| `sessionId` | texto | Identificador de sesión (se devuelve tal cual) |

> 💡 Para mejores resultados, enviá la imagen del **dorso**, que es donde está
> el MRZ. El frente solo se usa como fallback.

**Ejemplo con `curl`:**

```bash
curl -X POST http://localhost:8000/api/v1/ocr/process \
  -u admin:una-clave-segura \
  -F "backImage=@dorso.jpg" \
  -F "sessionId=mi-sesion-123"
```

**Respuesta de ejemplo:**

```json
{
  "sessionId": "mi-sesion-123",
  "status": "approved",
  "validations": [],
  "data": {
    "name": "Alan Gabriel",
    "lastName": "Sanjurjo",
    "dni": "42584758",
    "documentNumber": "42584758",
    "birthDate": "2001-11-07",
    "expiryDate": "2032-01-04",
    "sex": "M",
    "nationality": "ARG",
    "country": "ARG",
    "documentType": "ID",
    "mrzValid": true,
    "isExpired": false
  }
}
```

### Validaciones

El campo `validations` lista advertencias o motivos. Casos contemplados:

- **Documento vencido** → `isExpired: true` y un mensaje (la fecha se compara
  contra el día actual en Mendoza, Argentina). El documento se aprueba igual,
  pero queda marcado para que el cliente decida.
- **Fecha de nacimiento ausente o futura** → advertencia.
- **MRZ con dígitos de control no validados** (`mrzValid: false`) → advertencia
  de posible error de lectura OCR.

### `GET /health`

Healthcheck **público** (sin autenticación). Devuelve `{"status": "ok"}` si la
API está viva. Lo consumen orquestadores (Docker/Kubernetes), balanceadores de
carga y sistemas de monitoreo para detectar caídas y reiniciar el servicio; **no
se llama a sí mismo**. El `Dockerfile` ya lo usa como `HEALTHCHECK`.

---

## Seguridad

- El endpoint de procesamiento usa **HTTP Basic**; las credenciales viajan
  codificadas en base64, por lo que **en producción la API debe estar detrás de
  HTTPS** (reverse proxy con TLS) para que no se puedan interceptar.
- Las credenciales se comparan con `secrets.compare_digest` (resistente a
  ataques de temporización) y nunca se hardcodean: se leen de variables de entorno.

---

## Tests

```bash
docker compose run --rm api pytest
```

Los tests cubren el parseo MRZ (Argentina y Chile), el formateo de nombres y las
validaciones de negocio.

---

## Notas y limitaciones

- El **número de identificación nacional** que se puede extraer depende del país:
  - 🇦🇷 Argentina: el DNI está incluido en el MRZ.
  - 🇨🇱 Chile: el MRZ **no** contiene el RUN, solo el número de serie del
    documento. El RUN solo aparece en el frente.
- El parseo de PDF lee **texto embebido**; no realiza OCR sobre PDFs escaneados.
- Las fechas de vencimiento se comparan con la zona horaria
  `America/Argentina/Mendoza`.
