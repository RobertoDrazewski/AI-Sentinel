"""Utilidades para probar una conexión RTSP/DVR y sacar una foto de prueba.

Pensado para cámaras chinas genéricas, DVRs y marcas tipo Hikvision/EZVIZ/Dahua/Reolink
que exponen un stream RTSP. No dependemos del SDK propietario de ninguna marca: todo
pasa por RTSP estándar vía OpenCV + FFmpeg.
"""
from __future__ import annotations

import base64
import os
import threading
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

# Evita que OpenCV/FFmpeg se cuelgue esperando un socket TCP muerto.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;5000000|max_delay;500000"
)

# Plantillas conocidas de URL RTSP por marca/familia. El usuario completa IP, usuario,
# contraseña y canal; esto es sólo para precargar el campo en el wizard del frontend.
BRAND_URL_TEMPLATES = {
    "ezviz_hikvision": [
        "rtsp://{user}:{password}@{ip}:{port}/Streaming/Channels/101",
        "rtsp://{user}:{password}@{ip}:{port}/h264/ch1/main/av_stream",
    ],
    "dahua": [
        "rtsp://{user}:{password}@{ip}:{port}/cam/realmonitor?channel=1&subtype=0",
    ],
    "reolink": [
        "rtsp://{user}:{password}@{ip}:{port}/h264Preview_01_main",
    ],
    "dvr_generico_cp_plus_xm": [
        "rtsp://{user}:{password}@{ip}:{port}/cam/realmonitor?channel=1&subtype=0",
        "rtsp://{user}:{password}@{ip}:{port}/live/ch00_0",
    ],
    "onvif_generico": [
        "rtsp://{user}:{password}@{ip}:{port}/onvif1",
    ],
    "generico": [
        "rtsp://{user}:{password}@{ip}:{port}/stream1",
    ],
}

DEFAULT_PORT = 554


@dataclass
class ConnectionResult:
    ok: bool
    message: str
    width: Optional[int] = None
    height: Optional[int] = None
    snapshot_base64: Optional[str] = None


def _try_open_and_grab(rtsp_url: str, result_holder: dict) -> None:
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    try:
        if not cap.isOpened():
            result_holder["ok"] = False
            result_holder["message"] = (
                "No se pudo abrir el stream. Revisá IP, puerto, usuario/contraseña y que "
                "la cámara esté en la misma red."
            )
            return
        ok, frame = cap.read()
        if not ok or frame is None:
            result_holder["ok"] = False
            result_holder["message"] = "Se conectó pero no llegó ningún frame de video."
            return

        h, w = frame.shape[:2]
        ok_enc, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        snapshot_b64 = base64.b64encode(buf.tobytes()).decode("utf-8") if ok_enc else None

        result_holder["ok"] = True
        result_holder["message"] = "Conexión exitosa."
        result_holder["width"] = w
        result_holder["height"] = h
        result_holder["snapshot_base64"] = snapshot_b64
    except Exception as exc:  # noqa: BLE001
        result_holder["ok"] = False
        result_holder["message"] = f"Error al conectar: {exc}"
    finally:
        cap.release()


def test_rtsp_connection(rtsp_url: str, timeout_seconds: float = 8.0) -> ConnectionResult:
    """Intenta abrir el stream con timeout real (cv2 puede colgarse si no se corta aparte)."""
    result_holder: dict = {}
    thread = threading.Thread(target=_try_open_and_grab, args=(rtsp_url, result_holder), daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        return ConnectionResult(
            ok=False,
            message=(
                "Tiempo de espera agotado. La cámara no respondió a tiempo "
                "(revisá que esté encendida y accesible en tu red local)."
            ),
        )

    return ConnectionResult(**result_holder) if result_holder else ConnectionResult(
        ok=False, message="No se obtuvo respuesta de la cámara."
    )


def build_rtsp_url(brand: str, ip: str, user: str, password: str, port: int = DEFAULT_PORT) -> list[str]:
    templates = BRAND_URL_TEMPLATES.get(brand, BRAND_URL_TEMPLATES["generico"])
    return [t.format(user=user, password=password, ip=ip, port=port) for t in templates]
