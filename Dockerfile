# Imagen de un solo servicio para Railway (o cualquier host basado en Docker):
# compila el frontend y lo sirve el propio backend FastAPI, así no hace falta
# correr/pagar dos servicios separados sólo para probar.
#
# IMPORTANTE -- esto despliega la app web (login, configuración, alertas, etc.),
# pero el video RTSP de la cámara/DVR vive en tu red local de casa. Un backend
# en la nube (Railway) no puede ver por sí solo una IP 192.168.x.x de tu casa,
# así que mientras no expongas esa cámara hacia afuera (o metas un túnel/VPN de
# por medio) el estado de la cámara en este deploy de prueba va a quedar en
# "error"/"conectando". Para una prueba rápida de la app en sí (login, zonas,
# Telegram, suscripción) no hace falta resolver esto todavía.

# --- Etapa 1: build del frontend (Vite/React) ---
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Etapa 2: backend (FastAPI) + frontend ya compilado ---
FROM python:3.11-slim AS runtime
WORKDIR /app

# Librerías de sistema que opencv-python-headless necesita en tiempo de
# ejecución dentro de una imagen "slim" (si faltan, el import de cv2 explota).
# curl hace falta en tiempo de BUILD para scripts/download_models.sh más abajo
# -- "slim" no lo trae instalado de entrada.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libglib2.0-0 libgomp1 ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Modelos de reconocimiento facial (YuNet + SFace, ~37MB) y pesos de YOLOv8n
# (~6MB): se descargan acá, en el build, para no depender de internet (ni de la
# latencia/fragilidad de un primer pedido lento) la primera vez que alguien usa
# la app ya desplegada.
RUN bash scripts/download_models.sh
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Frontend ya compilado (de la etapa anterior) -- ver app/main.py: si esta
# carpeta existe, FastAPI la sirve directo, mismo dominio que la API.
COPY --from=frontend-build /app/frontend/dist ./static_frontend

ENV PORT=8000
EXPOSE 8000

# Railway (y la mayoría de los PaaS basados en contenedores) inyectan PORT en
# tiempo de ejecución, por eso el shell form (no el exec form) para que se
# expanda la variable.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
