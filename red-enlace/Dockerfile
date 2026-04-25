FROM node:20-alpine

# Usuario no-root
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodeapp -u 1001 -G nodejs

WORKDIR /app

# Copiar dependencias primero (cache optimizado)
COPY package*.json ./

# Instalar dependencias (más seguro usar npm install si no tienes lock)
RUN npm install --only=production && \
    npm cache clean --force

# Copiar todo el proyecto
COPY . .

# Cambiar usuario
USER nodeapp

# Puertos
EXPOSE 5454
EXPOSE 8000

# Inicio
CMD ["node", "server.js"]