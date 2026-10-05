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

# Cómo abrimos el stream con FFmpeg: ver open_capture_with_fallback() más abajo.
# OpenCV no tiene una API por-captura para esta opción -- la única forma de pasarle
# "rtsp_transport" a FFmpeg es esta variable de entorno de PROCESO, así que el valor
# se pisa justo antes de cada intento de apertura (no se deja un default fijo acá).
_RTSP_TRANSPORTS = ("tcp", "udp")
_transport_lock = threading.Lock()


def _set_ffmpeg_transport(transport: str) -> None:
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        f"rtsp_transport;{transport}|stimeout;5000000|max_delay;500000"
    )


def open_capture_with_fallback(rtsp_url: str) -> "tuple[Optional[cv2.VideoCapture], str]":
    """Abre un VideoCapture RTSP probando TCP primero y, si falla, UDP.

    Por qué hace falta esto: forzábamos sólo rtsp_transport=tcp (más robusto en general
    frente a una red con pérdida de paquetes, y evita que FFmpeg se cuelgue esperando un
    socket UDP muerto) -- pero hay cámaras, sobre todo EZVIZ/Hikvision de consumo, cuyo
    firmware RTSP no responde bien por TCP y rechazan la conexión al toque (cap.isOpened()
    da False enseguida, no es un timeout). El mismo stream en esos casos abre sin problema
    en VLC, porque VLC negocia el transporte solo y cae a UDP si hace falta. Probamos TCP
    primero igual -- sigue siendo la opción más confiable cuando SÍ funciona -- y sólo si
    eso falla reintentamos una vez por UDP antes de darnos por vencidos.

    El lock es porque la variable de entorno es de PROCESO, no por-captura: dos cámaras
    abriendo al mismo tiempo en hilos distintos (ver camera_worker.py, un hilo por cámara)
    podrían pisarse la una a la otra si no se serializa. Se toma SOLO durante el intento de
    apertura -- cap.read() de ahí en más ya no depende de esta variable -- así que no frena
    el resto del pipeline de video.

    Devuelve (cap, transporte_usado). cap es None si ninguno de los dos transportes abrió.
    """
    last_transport = _RTSP_TRANSPORTS[0]
    with _transport_lock:
        for transport in _RTSP_TRANSPORTS:
            last_transport = transport
            _set_ffmpeg_transport(transport)
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            if cap.isOpened():
                return cap, transport
            cap.release()
    return None, last_transport


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
    cap, _transport = open_capture_with_fallback(rtsp_url)
    try:
        if cap is None:
            result_holder["ok"] = False
            result_holder["message"] = (
                "No se pudo abrir el stream (se probó por TCP y por UDP). Revisá IP, puerto, "
                "usuario/contraseña y que la cámara esté en la misma red."
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
        if cap is not None:
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
