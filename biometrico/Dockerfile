FROM python:3.11-alpine

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# dependencias del sistema
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev

# requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# código
COPY . .

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "server-biometrico:app"]