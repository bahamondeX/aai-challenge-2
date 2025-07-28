# === STAGE 1: Build Vue app ===
FROM node:20-alpine AS build-stage

WORKDIR /app

# Copia solo los archivos necesarios para instalar y compilar Vue
COPY . .

# Instala dependencias y compila el frontend
RUN npm i -g pnpm && pnpm install && pnpm run build

# === STAGE 2: FastAPI backend with built frontend ===
FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Copia backend (FastAPI) archivos
COPY main.py requirements.txt cookies.txt /app/

# Copia build generado por Vue
COPY --from=build-stage /app/dist ./dist

# Instala dependencias Python
RUN pip install -r requirements.txt

# Exponer puerto requerido por Cloud Run
EXPOSE 8080

# Comando para ejecutar el servidor
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]