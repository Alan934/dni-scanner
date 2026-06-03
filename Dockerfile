FROM python:3.10-slim

WORKDIR /app

ENV FLAGS_use_mkldnn=0
ENV PADDLE_USE_MKLDNN=0

# Dependencias del sistema
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Actualizamos pip y damos 1000 segundos de tiempo de espera
RUN pip install --upgrade pip && \
    pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]