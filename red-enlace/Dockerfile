FROM node:20-alpine

# Crear usuario no-root por seguridad
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodeapp -u 1001 -G nodejs

WORKDIR /app

# Copiar package.json primero para cachear dependencias
COPY package*.json ./

RUN npm ci --only=production && \
    npm cache clean --force
COPY requirements.txt .
COPY . .

# Cambiar a usuario no-root
USER nodeapp

# === PUERTOS CORREGIDOS (sin comentarios en la misma línea) ===
EXPOSE 5454
EXPOSE 8000

# Comando de inicio
CMD ["node", "server.js"]   