"""Detección de personas y vehículos con YOLOv8n (ultralytics).

Se usa el modelo nano pre-entrenado en COCO: liviano y corre bien en CPU.
Clases COCO relevantes: 0=person, 2=car, 3=motorcycle, 5=bus, 7=truck.
"""
from __future__ import annotations

from typing import List, NamedTuple, Tuple

import cv2
import numpy as np

_model = None

COCO_PERSON = 0
COCO_CAR = 2
COCO_MOTORCYCLE = 3
COCO_BUS = 5
COCO_TRUCK = 7

VEHICLE_CLASSES = {COCO_CAR, COCO_MOTORCYCLE, COCO_BUS, COCO_TRUCK}


class Detection(NamedTuple):
    cls_id: int
    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def centroid(self):
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


def _get_model():
    global _model
    if _model is None:
        from ultralytics import YOLO  # import diferido: es pesado, sólo cuando hace falta

        _model = YOLO("yolov8n.pt")  # se descarga solo la primera vez (~6MB)
    return _model


def looks_red(frame: np.ndarray, bbox: Tuple[int, int, int, int], min_ratio: float = 0.12) -> bool:
    """Heurística simple de color: ¿hay una porción grande roja dentro de este cuadro?
    Pensado para la caja/mochila roja típica de apps de delivery (ej. PedidosYa) en el
    palier trasero de una moto. Es sólo color, no reconocimiento de marca/logo, así que
    puede confundir con otras cosas rojas (una campera, un auto rojo) — es una pista
    extra para la alerta, no una certeza."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return False
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return False
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    # El rojo en HSV (OpenCV usa H en 0-179) está partido en dos franjas, cerca de 0 y de 179.
    lower1, upper1 = np.array([0, 90, 60]), np.array([10, 255, 255])
    lower2, upper2 = np.array([160, 90, 60]), np.array([179, 255, 255])
    mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)
    ratio = float(np.count_nonzero(mask)) / mask.size
    return ratio >= min_ratio


def detect(frame: np.ndarray, confidence: float = 0.4) -> List[Detection]:
    model = _get_model()
    results = model.predict(frame, verbose=False, conf=confidence, classes=list({COCO_PERSON} | VEHICLE_CLASSES))
    detections: List[Detection] = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            label = model.names.get(cls_id, str(cls_id))
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            detections.append(Detection(cls_id, label, conf, x1, y1, x2, y2))
    return detections
