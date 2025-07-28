# === STAGE 1: Build Vue app ===
FROM node:20-alpine AS build-stage

WORKDIR /app
COPY . .

RUN npm i -g pnpm && pnpm install && pnpm run build

# === STAGE 2: FastAPI backend with built frontend ===
FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Copia backend y archivo de cookies base64
COPY main.py requirements.txt cookies.txt /app/

# Copia el frontend generado
COPY --from=build-stage /app/dist ./dist

# Instala dependencias
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]