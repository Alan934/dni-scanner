FROM python:3.10-slim

WORKDIR /code

# Desactiva OneDNN para evitar un crash de Paddle en CPU.
ENV FLAGS_use_mkldnn=0
ENV PADDLE_USE_MKLDNN=0
# Evita que Python genere .pyc y fuerza logs sin buffer.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dependencias del sistema necesarias para OpenCV / PaddleOCR.
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Instalamos dependencias primero para aprovechar la cache de capas de Docker.
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# Copiamos el código de la aplicación y los tests.
COPY app/ ./app/
COPY tests/ ./tests/

EXPOSE 8000

# El orquestador usa /health para saber si el contenedor está sano y reiniciarlo
# si deja de responder. start-period da tiempo a que cargue el modelo de OCR.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
