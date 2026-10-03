"""Loop principal por cámara: lee el RTSP, corre detección de objetos/caras,
aplica la lógica de zonas (permanencia, vehículo detenido, manipulación de reja),
dispara alertas y deja el último frame anotado disponible para el streaming MJPEG."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import cv2
import numpy as np
from sqlmodel import Session, select

from app.database import engine
from app.models import Camera, KnownFace, Zone
from app.vision import face_engine, object_detector, rtsp_utils
from app.vision.alert_manager import raise_alert
from app.vision.gate_tamper import GateTamperDetector
from app.vision.zone_tracker import CentroidTracker, point_in_polygon

DETECT_EVERY_N_FRAMES = 5
FACE_EVERY_N_FRAMES = 10
MIN_FACE_WIDTH_RATIO = 0.035  # ~3.5% del ancho del frame: se adapta a la resolución de cada cámara

VEHICLE_LABELS_ES = {"car": "Auto", "motorcycle": "Moto", "bus": "Colectivo", "truck": "Camión"}

# Defensa contra el "destello blanco" típico de frames I-frame corruptos en RTSP
# por wifi/DVR inestable: si un frame es mucho más claro que el promedio reciente,
# lo tratamos como corrupto y lo salteamos en vez de mostrarlo/procesarlo.
BRIGHTNESS_SPIKE_ABS = 215
BRIGHTNESS_SPIKE_RATIO = 1.6

ZONE_COLORS = {"reja": (0, 165, 255), "calle": (255, 191, 0), "custom": (0, 255, 0), "timbre": (255, 0, 255)}


@dataclass
class WorkerState:
    thread: threading.Thread
    stop_event: threading.Event
    latest_jpeg: Optional[bytes] = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    status: str = "iniciando"
    user_id: Optional[int] = None
    face_index: Optional["face_engine.KnownFaceIndex"] = None


def reload_known_faces(user_id: int) -> None:
    """Hace que las cámaras de este usuario que ya están monitoreando relean la
    lista de rostros conocidos desde la base, sin tener que reiniciar el monitoreo.
    Se llama después de subir o borrar una foto en /api/faces — si no, una cámara
    que ya estaba corriendo nunca se entera de las caras nuevas."""
    with Session(engine) as session:
        rows = session.exec(select(KnownFace).where(KnownFace.user_id == user_id)).all()
        pairs = [(f.name, f.embedding_json) for f in rows]
    for state in _workers.values():
        if state.user_id == user_id and state.face_index is not None:
            state.face_index.load(pairs)


_workers: Dict[int, WorkerState] = {}


def start_worker(camera_id: int) -> None:
    if camera_id in _workers and _workers[camera_id].thread.is_alive():
        return  # ya está corriendo
    stop_event = threading.Event()
    thread = threading.Thread(target=_run_loop, args=(camera_id, stop_event), daemon=True)
    state = WorkerState(thread=thread, stop_event=stop_event)
    _workers[camera_id] = state
    thread.start()


def stop_worker(camera_id: int) -> None:
    state = _workers.get(camera_id)
    if state:
        state.stop_event.set()


def get_latest_jpeg(camera_id: int) -> Optional[bytes]:
    state = _workers.get(camera_id)
    if not state:
        return None
    with state.lock:
        return state.latest_jpeg


def get_status(camera_id: int) -> str:
    state = _workers.get(camera_id)
    return state.status if state else "detenida"


def _polygon_to_px(polygon_relative: List[List[float]], w: int, h: int) -> List[tuple]:
    return [(int(x * w), int(y * h)) for x, y in polygon_relative]


def _zone_mask(polygon_px: List[tuple], w: int, h: int) -> np.ndarray:
    mask = np.zeros((h, w), dtype=np.uint8)
    if len(polygon_px) >= 3:
        cv2.fillPoly(mask, [np.array(polygon_px, dtype=np.int32)], 255)
    return mask


def _draw_dwell_counter(frame: np.ndarray, bbox, secs: float, threshold: float) -> None:
    """Dibuja "Ns / Ms" arriba del cuadro de un objeto mientras está dentro de una
    zona con permanencia/vehículo detenido activado. Pensado como ayuda para ver a
    simple vista, en el video en vivo, que la detección y el cronómetro están
    funcionando -- sin esto, un auto/persona detenido es un cronómetro invisible
    hasta que la alerta (o no) llega a Telegram varios segundos/minutos después."""
    x1, y1, _, _ = bbox
    text = f"{int(secs)}s / {int(threshold)}s"
    color = (0, 255, 255) if secs < threshold else (0, 0, 255)
    cv2.putText(frame, text, (max(0, x1), max(15, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def _load_camera_context(camera_id: int):
    with Session(engine) as session:
        camera = session.get(Camera, camera_id)
        if not camera:
            return None
        zones = session.exec(select(Zone).where(Zone.camera_id == camera_id)).all()
        known_faces = session.exec(
            select(KnownFace).where(KnownFace.user_id == camera.user_id)
        ).all()
        return camera, zones, known_faces


def _set_camera_status(camera_id: int, status: str) -> None:
    with Session(engine) as session:
        camera = session.get(Camera, camera_id)
        if camera:
            camera.status = status
            session.add(camera)
            session.commit()


def _run_loop(camera_id: int, stop_event: threading.Event) -> None:
    state = _workers[camera_id]
    ctx = _load_camera_context(camera_id)
    if not ctx:
        state.status = "error"
        return
    camera, zones, known_faces_rows = ctx

    face_index = face_engine.KnownFaceIndex()
    face_index.load([(f.name, f.embedding_json) for f in known_faces_rows])
    state.user_id = camera.user_id
    state.face_index = face_index

    tracker = CentroidTracker()
    # Zonas "timbre" (mano cruzando una zona chica) necesitan reaccionar a un gesto
    # de menos de un segundo; "reja" espera manipulación sostenida (alguien forzando/
    # tironeando), que lleva más tiempo real. Por eso un umbral de segundos bien
    # distinto para cada una (ver gate_tamper.py: ahora mide tiempo real, no "N
    # llamadas seguidas", que fallaba para gestos cortos).
    gate_detectors: Dict[int, GateTamperDetector] = {
        z.id: GateTamperDetector(min_sustained_seconds=0.12 if z.kind == "timbre" else 1.5)
        for z in zones
        if z.detect_gate_tamper
    }

    cap: Optional[cv2.VideoCapture] = None
    reconnect_wait = 3
    frame_count = 0
    baseline_brightness: Optional[float] = None

    while not stop_event.is_set():
        if cap is None or not cap.isOpened():
            state.status = "conectando"
            cap = cv2.VideoCapture(camera.rtsp_url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                _set_camera_status(camera_id, "error")
                state.status = "error"
                time.sleep(reconnect_wait)
                reconnect_wait = min(reconnect_wait * 2, 30)
                continue
            reconnect_wait = 3
            _set_camera_status(camera_id, "conectada")

        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            cap = None
            time.sleep(1)
            continue

        # Frame corrupto/destello: lo detectamos por un salto brusco de brillo
        # promedio y lo salteamos entero (no se muestra ni se procesa), para no
        # ensuciar la vista ni disparar falsos positivos con un frame basura.
        mean_brightness = float(frame.mean())
        if baseline_brightness is None:
            baseline_brightness = mean_brightness
        is_flash_frame = (
            mean_brightness > BRIGHTNESS_SPIKE_ABS
            and mean_brightness > baseline_brightness * BRIGHTNESS_SPIKE_RATIO
        )
        if is_flash_frame:
            time.sleep(0.01)
            continue
        baseline_brightness = baseline_brightness * 0.95 + mean_brightness * 0.05

        state.status = "monitoreando"
        h, w = frame.shape[:2]
        frame_count += 1
        display_frame = frame.copy()

        zones_px = {
            z.id: _polygon_to_px(json.loads(z.polygon_json), w, h) for z in zones
        }

        # --- Dibuja las zonas siempre, haya o no detección este frame ---
        for z in zones:
            poly = zones_px[z.id]
            if len(poly) >= 3:
                # Las zonas marcadas como "tapa mi salida" se dibujan en rojo para
                # distinguirlas de un vistazo de una zona de estacionamiento normal.
                color = (0, 0, 255) if z.blocks_exit else ZONE_COLORS.get(z.kind, (0, 255, 0))
                cv2.polylines(display_frame, [np.array(poly, dtype=np.int32)], True, color, 2)
                cv2.putText(
                    display_frame, z.name, poly[0], cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
                )

        # --- Detección de objetos (personas / vehículos) cada N frames ---
        if frame_count % DETECT_EVERY_N_FRAMES == 0:
            detections = object_detector.detect(frame)
            tracked = tracker.update(detections)

            for det in detections:
                cv2.rectangle(display_frame, (det.x1, det.y1), (det.x2, det.y2), (0, 255, 0), 1)

            is_vehicle_label = lambda label: label in {"car", "motorcycle", "bus", "truck"}

            for obj in tracked:
                for z in zones:
                    poly = zones_px[z.id]
                    if len(poly) < 3:
                        continue
                    inside = point_in_polygon(obj.centroid, poly)

                    if obj.label == "person" and z.detect_people:
                        secs = tracker.time_in_zone(obj, z.id, inside)
                        if inside and obj.bbox is not None:
                            _draw_dwell_counter(display_frame, obj.bbox, secs, z.loiter_seconds)
                        if secs >= z.loiter_seconds and not obj.zone_alerted.get(z.id):
                            obj.zone_alerted[z.id] = True
                            msg = (
                                f"🕐 *Permanencia sospechosa* en \"{z.name}\": alguien parado "
                                f"ahí hace más de {int(z.loiter_seconds)}s."
                            )
                            raise_alert(
                                camera.user_id, camera_id, "permanencia", display_frame,
                                zone_id=z.id, message_override=msg,
                            )

                    if is_vehicle_label(obj.label) and z.detect_vehicles:
                        secs = tracker.time_in_zone(obj, z.id, inside)
                        if inside and obj.bbox is not None:
                            _draw_dwell_counter(display_frame, obj.bbox, secs, z.vehicle_stop_seconds)
                        if secs >= z.vehicle_stop_seconds and not obj.zone_alerted.get(z.id):
                            obj.zone_alerted[z.id] = True
                            vehicle_txt = VEHICLE_LABELS_ES.get(obj.label, obj.label)
                            stopped_for = int(z.vehicle_stop_seconds)
                            tiempo_txt = f"{stopped_for // 60} min" if stopped_for >= 60 and stopped_for % 60 == 0 else f"{stopped_for}s"
                            is_red_box = (
                                obj.label == "motorcycle"
                                and obj.bbox is not None
                                and object_detector.looks_red(frame, obj.bbox)
                            )
                            if z.blocks_exit:
                                alert_type = "vehiculo_bloqueando_salida"
                                msg = (
                                    f"🔴🚨 *¡Puente ocupado!* {vehicle_txt} parado hace {tiempo_txt} "
                                    f"en \"{z.name}\"."
                                )
                            else:
                                alert_type = "vehiculo_detenido"
                                msg = f"🚗 *{vehicle_txt} detenido hace {tiempo_txt}* en \"{z.name}\"."
                            if is_red_box:
                                msg += " Tiene una caja/baúl roja visible (podría ser un repartidor)."
                            raise_alert(
                                camera.user_id, camera_id, alert_type, display_frame,
                                zone_id=z.id, message_override=msg,
                            )

        # --- Movimiento sobre zonas chicas (flujo óptico): reja o timbre ---
        # Corre en CADA frame crudo (no cada N como la detección de objetos): un
        # gesto corto como tocar el timbre puede durar bien menos de un segundo, y
        # si sólo mirábamos 1 de cada 5 frames nos lo podíamos perder entero. El
        # flujo óptico sobre una zona chica es liviano, así que correrlo siempre no
        # debería notarse en el uso de CPU.
        if gate_detectors:
            for z in zones:
                detector = gate_detectors.get(z.id)
                if detector is None:
                    continue
                mask = _zone_mask(zones_px[z.id], w, h)
                triggered = detector.update(frame, mask)
                if triggered:
                    if z.kind == "timbre":
                        msg = (
                            f"🔔 *Movimiento en \"{z.name}\"* — parece que alguien tocó o se "
                            f"acercó a la puerta."
                        )
                        raise_alert(
                            camera.user_id, camera_id, "timbre", display_frame,
                            zone_id=z.id, message_override=msg,
                        )
                    else:
                        msg = f"🚨 *Posible manipulación* detectada en \"{z.name}\"."
                        raise_alert(
                            camera.user_id, camera_id, "manipulacion_reja", display_frame,
                            zone_id=z.id, message_override=msg,
                        )

        # --- Reconocimiento facial (más caro, cada FACE_EVERY_N_FRAMES) ---
        if frame_count % FACE_EVERY_N_FRAMES == 0 and face_engine.models_available():
            faces = face_engine.detect_faces(frame)
            min_face_width = max(24, int(w * MIN_FACE_WIDTH_RATIO))
            for face_row in faces:
                x, y, fw, fh = face_row[:4].astype(int)
                if fw < min_face_width:
                    continue  # muy chica / muy lejos, evita falsos positivos de la calle
                embedding = face_engine.get_embedding(frame, face_row)
                match = face_index.match(embedding)
                color = (0, 255, 0) if match else (0, 0, 255)
                cv2.rectangle(display_frame, (x, y), (x + fw, y + fh), color, 2)
                if match:
                    cv2.putText(display_frame, match, (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    raise_alert(camera.user_id, camera_id, "familiar", display_frame, detail=match)
                else:
                    cv2.putText(display_frame, "desconocido", (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    raise_alert(camera.user_id, camera_id, "intruso", display_frame)

        ok_enc, buf = cv2.imencode(".jpg", display_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ok_enc:
            with state.lock:
                state.latest_jpeg = buf.tobytes()

        time.sleep(0.01)

    if cap is not None:
        cap.release()
    _set_camera_status(camera_id, "desconectada")
    state.status = "detenida"
