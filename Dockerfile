FROM node:20-alpine

# Crear usuario no-root por seguridad
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodeapp -u 1001 -G nodejs

WORKDIR /app

# Copiar package.json primero para cachear dependencias
COPY package*.json ./

RUN npm ci --only=production && \
    npm cache clean --force

COPY . .

# Cambiar a usuario no-root
USER nodeapp

# Puertos expuestos
EXPOSE 5454
EXPOSE 8000
EXPOSE 9000

# Comando de inicio (ejecutar múltiples servidores)
CMD ["sh", "-c", "node server.js & node server-biometrico.js & wait"]