#!/usr/bin/env bash
# Levanta el backend en localhost:8000. Crea el venv e instala dependencias
# la primera vez que lo corrés.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d "venv" ]; then
  echo "Creando entorno virtual..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "No hay .env, copio .env.example -> .env (después completá tus credenciales)."
  cp .env.example .env
fi

if [ ! -f "app/models_data/face_recognition_sface_2021dec.onnx" ]; then
  echo "Descargando modelos de reconocimiento facial (primera vez, ~37MB)..."
  bash scripts/download_models.sh
fi

echo "Arrancando backend en http://localhost:8000 (docs en /docs)..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
