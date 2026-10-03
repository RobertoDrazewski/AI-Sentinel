"""Heurística simple para detectar manipulación de la reja, o una mano cruzando una
zona chica tipo timbre (v3).

Esto NO es pose estimation ni detección de "brazo cruzando los barrotes" real:
es un prototipo basado en flujo óptico. Mide cuánto tiempo REAL (no cantidad de
llamadas) hay movimiento sostenido dentro de la zona.

v1 contaba "N llamadas seguidas con movimiento" en vez de tiempo real, lo que se
rompía para gestos cortos (ver historial). v2 pasó a medir tiempo real, pero al
correr en cada frame crudo (necesario para no perderse un toque de timbre de <1s)
empezó a enganchar ruido de sensor/grano IR nocturno como si fuera movimiento real
-- de noche, con poca luz, la cámara sube la ganancia y el grano pixel a pixel puede
alcanzar para inflar un PROMEDIO de movimiento aunque en la imagen no cambie nada a
simple vista. v3 agrega dos defensas para eso:
  1. Un desenfoque (GaussianBlur) antes de calcular flujo óptico, que amortigua
     ruido fino pixel a pixel sin borrar un movimiento real de verdad.
  2. En vez de mirar el PROMEDIO de movimiento en la zona (que un ruido parejo de
     grano puede inflar sin que haya nada realmente moviéndose), exigimos que una
     PORCIÓN mínima de la zona muestre movimiento franco (por encima del umbral por
     píxel). Una mano o un portón moviéndose ocupa una parte grande y compacta de la
     zona; el ruido de grano, en cambio, suele estar disperso y parejo.
"""
from __future__ import annotations

import time
from typing import Optional

import cv2
import numpy as np


class GateTamperDetector:
    def __init__(
        self,
        min_sustained_seconds: float = 1.5,
        motion_threshold: float = 2.5,
        min_moving_ratio: float = 0.15,
    ):
        self._prev_gray: Optional[np.ndarray] = None
        self._motion_start: Optional[float] = None
        self.min_sustained_seconds = min_sustained_seconds
        # Umbral de magnitud de flujo óptico POR PÍXEL (no promedio) para contar ese
        # píxel como "en movimiento".
        self.motion_threshold = motion_threshold
        # Qué fracción de la zona tiene que estar "en movimiento" para contarlo como
        # un evento real, en vez de ruido disperso.
        self.min_moving_ratio = min_moving_ratio

    def update(self, frame: np.ndarray, zone_mask: np.ndarray) -> bool:
        """zone_mask: máscara binaria (mismo tamaño que frame) con 255 en la zona.
        Devuelve True apenas el movimiento lleva min_sustained_seconds sostenido."""
        now = time.time()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        gray = cv2.resize(gray, (frame.shape[1] // 2, frame.shape[0] // 2))
        mask_small = cv2.resize(zone_mask, (gray.shape[1], gray.shape[0]))

        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            self._prev_gray = gray
            return False

        flow = cv2.calcOpticalFlowFarneback(
            self._prev_gray, gray, None, 0.5, 2, 15, 3, 5, 1.2, 0
        )
        self._prev_gray = gray

        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        masked_mag = mag[mask_small > 0]
        if masked_mag.size == 0:
            self._motion_start = None
            return False

        moving_ratio = float(np.count_nonzero(masked_mag > self.motion_threshold)) / masked_mag.size

        if moving_ratio > self.min_moving_ratio:
            if self._motion_start is None:
                self._motion_start = now
            return (now - self._motion_start) >= self.min_sustained_seconds
        else:
            self._motion_start = None
            return False
