FROM node:20-alpine

# Instalar wget para healthcheck
RUN apk add --no-cache wget

# Crear usuario no-root por seguridad
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodeapp -u 1001 -G nodejs

WORKDIR /app

# Copiar package.json primero para cachear dependencias
COPY package*.json ./

# Instalar dependencias
RUN npm ci --only=production && \
    npm cache clean --force

# Copiar código fuente
COPY . .

# Cambiar permisos
RUN chown -R nodeapp:nodejs /app

# Cambiar a usuario no-root
USER nodeapp

# Exponer puertos
EXPOSE 5454
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8000/health || exit 1

# Comando de inicio
CMD ["node", "server.js"]