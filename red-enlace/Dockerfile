FROM node:20-alpine

WORKDIR /app

# Crear package.json automáticamente si no existe
RUN npm init -y

# (Opcional) instala dependencias básicas si las necesitas
# EJEMPLO: si usas express
RUN npm install express

# Copiar tu código
COPY . .

# Limpiar cache
RUN npm cache clean --force

# Usar usuario node (ya existe en la imagen)
USER node

EXPOSE 5454
EXPOSE 8000

CMD ["node", "server.js"]