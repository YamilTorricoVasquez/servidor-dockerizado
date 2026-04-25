FROM python:3.11-alpine

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Exponer puerto (ejemplo Flask)
EXPOSE 5000

# Ejecutar servidor
CMD ["python", "server-biometrico.py"]