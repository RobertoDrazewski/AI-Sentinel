"""Tracking simple por centroide + lógica de permanencia (loitering) por zona.

No es un tracker de nivel producción (tipo DeepSORT), pero alcanza para un prototipo:
asocia detecciones entre frames por cercanía de centroide y mide cuánto tiempo lleva
un objeto dentro de cada zona para decidir si es "alguien que pasa caminando" o
"alguien parado frente a la reja".
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """Ray casting clásico. polygon y point en las mismas unidades (píxeles o relativas)."""
    x, y = point
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


@dataclass
class TrackedObject:
    track_id: int
    label: str
    centroid: Tuple[float, float]
    last_seen: float = field(default_factory=time.time)
    zone_enter_time: Dict[int, float] = field(default_factory=dict)  # zone_id -> timestamp
    zone_alerted: Dict[int, bool] = field(default_factory=dict)  # zone_id -> ya se avisó
    # Último cuadro (x1,y1,x2,y2) donde se vio este objeto. Se usa, por ejemplo, para
    # mirar el color dentro del cuadro de una moto (caja roja tipo delivery).
    bbox: Optional[Tuple[int, int, int, int]] = None


class CentroidTracker:
    """Tracker mínimo: asocia por distancia euclídea al centroide más cercano."""

    def __init__(self, max_distance: float = 80.0, max_age_seconds: float = 2.0):
        self.next_id = 1
        self.objects: Dict[int, TrackedObject] = {}
        self.max_distance = max_distance
        self.max_age_seconds = max_age_seconds

    def update(self, detections) -> List[TrackedObject]:
        now = time.time()
        unmatched = list(detections)
        used_ids = set()

        for det in list(unmatched):
            best_id = None
            best_dist = self.max_distance
            for obj_id, obj in self.objects.items():
                if obj_id in used_ids or obj.label != det.label:
                    continue
                dist = np.hypot(obj.centroid[0] - det.centroid[0], obj.centroid[1] - det.centroid[1])
                if dist < best_dist:
                    best_dist = dist
                    best_id = obj_id
            if best_id is not None:
                obj = self.objects[best_id]
                obj.centroid = det.centroid
                obj.last_seen = now
                obj.bbox = (det.x1, det.y1, det.x2, det.y2)
                used_ids.add(best_id)
                unmatched.remove(det)

        for det in unmatched:
            obj = TrackedObject(
                track_id=self.next_id,
                label=det.label,
                centroid=det.centroid,
                last_seen=now,
                bbox=(det.x1, det.y1, det.x2, det.y2),
            )
            self.objects[self.next_id] = obj
            self.next_id += 1

        stale_ids = [oid for oid, obj in self.objects.items() if now - obj.last_seen > self.max_age_seconds]
        for oid in stale_ids:
            del self.objects[oid]

        return list(self.objects.values())

    def time_in_zone(self, obj: TrackedObject, zone_id: int, point_inside: bool) -> float:
        """Actualiza y devuelve cuántos segundos lleva el objeto dentro de la zona."""
        now = time.time()
        if point_inside:
            if zone_id not in obj.zone_enter_time:
                obj.zone_enter_time[zone_id] = now
            return now - obj.zone_enter_time[zone_id]
        else:
            obj.zone_enter_time.pop(zone_id, None)
            obj.zone_alerted.pop(zone_id, None)
            return 0.0
