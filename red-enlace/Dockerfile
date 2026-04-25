FROM node:20-alpine

# Usuario no-root
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodeapp -u 1001 -G nodejs

WORKDIR /app

# Copiar todo el código primero (incluye server.js si existe)
COPY . .

# Crear package.json automáticamente si no existe
RUN npm init -y

# Instalar dependencias necesarias
RUN npm install express --only=production && \
    npm cache clean --force
COPY requirements.txt .
# Cambiar a usuario no-root
USER nodeapp

# Puertos
EXPOSE 5454
EXPOSE 8000

# Inicio
CMD ["node", "server.js"]