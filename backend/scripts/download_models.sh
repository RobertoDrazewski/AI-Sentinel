#!/usr/bin/env bash
# Descarga los modelos livianos de reconocimiento facial (YuNet + SFace) desde
# opencv_zoo. Se corren una sola vez. Total: ~37 MB.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
MODELS_DIR="$BACKEND_DIR/app/models_data"

mkdir -p "$MODELS_DIR"

YUNET_URL="https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL="https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

echo "Descargando detector de rostros (YuNet)..."
curl -L --fail -o "$MODELS_DIR/face_detection_yunet_2023mar.onnx" "$YUNET_URL"

echo "Descargando reconocedor de identidad (SFace)..."
curl -L --fail -o "$MODELS_DIR/face_recognition_sface_2021dec.onnx" "$SFACE_URL"

echo "Listo. Modelos guardados en $MODELS_DIR"
