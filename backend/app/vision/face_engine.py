"""Reconocimiento facial liviano con los modelos YuNet (detección) + SFace (identidad)
que vienen en opencv-python (desde la 4.5.4 ya están en el paquete base, no hace falta
el contrib) / modelos de opencv_zoo. No requiere dlib ni compilar nada.

Modelos (se descargan una sola vez con scripts/download_models.sh):
  - face_detection_yunet_2023mar.onnx   (~340 KB)
  - face_recognition_sface_2021dec.onnx (~36 MB)
"""
from __future__ import annotations

import json
import os
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.config import settings

YUNET_PATH = os.path.join(settings.MODELS_DIR, "face_detection_yunet_2023mar.onnx")
SFACE_PATH = os.path.join(settings.MODELS_DIR, "face_recognition_sface_2021dec.onnx")

MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.30"))
# El valor "de libro" de opencv_zoo para similitud coseno de SFace es 0.363, calibrado
# con fotos de referencia en buenas condiciones de estudio. En la práctica, una cámara
# de exterior (ángulo distinto al de una selfie, contraluz, menos nitidez) baja el score
# incluso para la misma persona, así que lo relajamos un poco por default. Si notás que
# reconoce como "familiar" a gente que no lo es, subí FACE_MATCH_THRESHOLD en el .env
# (hacia 0.363 o más). La forma más confiable de mejorar esto de fondo es subir fotos
# de referencia con /from-camera (ver abajo), que capturan la cara con la misma luz y
# ángulo que la cámara va a ver en vivo, en vez de depender sólo del umbral.

_detector = None
_recognizer = None


def models_available() -> bool:
    return os.path.exists(YUNET_PATH) and os.path.exists(SFACE_PATH)


def _get_detector(frame_w: int, frame_h: int):
    global _detector
    if _detector is None:
        _detector = cv2.FaceDetectorYN.create(YUNET_PATH, "", (frame_w, frame_h), score_threshold=0.75)
    else:
        _detector.setInputSize((frame_w, frame_h))
    return _detector


def _get_recognizer():
    global _recognizer
    if _recognizer is None:
        _recognizer = cv2.FaceRecognizerSF.create(SFACE_PATH, "")
    return _recognizer


def detect_faces(frame: np.ndarray) -> List[np.ndarray]:
    """Devuelve una lista de filas 'faces' tal como las da YuNet: [x,y,w,h,5 landmarks,score]."""
    if not models_available():
        return []
    h, w = frame.shape[:2]
    detector = _get_detector(w, h)
    _, faces = detector.detect(frame)
    if faces is None:
        return []
    return list(faces)


def get_embedding(frame: np.ndarray, face_row: np.ndarray) -> np.ndarray:
    recognizer = _get_recognizer()
    aligned = recognizer.alignCrop(frame, face_row)
    return recognizer.feature(aligned)


def compare_embeddings(emb1: np.ndarray, emb2: np.ndarray) -> float:
    recognizer = _get_recognizer()
    return float(recognizer.match(emb1, emb2, cv2.FaceRecognizerSF_FR_COSINE))


class KnownFaceIndex:
    """Índice en memoria de rostros conocidos (familiares) para un usuario."""

    def __init__(self):
        self.names: List[str] = []
        self.embeddings: List[np.ndarray] = []

    def load(self, known_faces: List[Tuple[str, Optional[str]]]):
        """known_faces: lista de (name, embedding_json)."""
        self.names = []
        self.embeddings = []
        for name, emb_json in known_faces:
            if not emb_json:
                continue
            arr = np.array(json.loads(emb_json), dtype=np.float32).reshape(1, -1)
            self.names.append(name)
            self.embeddings.append(arr)

    def match(self, embedding: np.ndarray) -> Optional[str]:
        best_name = None
        best_score = -1.0
        for name, known_emb in zip(self.names, self.embeddings):
            score = compare_embeddings(embedding, known_emb)
            if score > best_score:
                best_score = score
                best_name = name
        if best_score >= MATCH_THRESHOLD:
            return best_name
        return None
