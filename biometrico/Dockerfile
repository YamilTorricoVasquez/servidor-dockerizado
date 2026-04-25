FROM python:3.11-alpine

WORKDIR /app

# Variables de entorno
ENV PYTHONUNBUFFERED=1

# Dependencias del sistema
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Exponer puerto
EXPOSE 5000

# Usar Gunicorn (PRODUCCIÓN)
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "server-biometrico:app"]