"""Crea alertas en la base, guarda la foto de respaldo y dispara Telegram.
Incluye un cooldown por (cámara, tipo) para no saturar al usuario con la misma
alerta repetida cada frame."""
from __future__ import annotations

import os
import time
import uuid
from typing import Optional

import cv2
import numpy as np
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.integrations.telegram_bot import enviar_alerta_telegram
from app.models import Alert, TelegramConfig

_last_alert_time: dict[tuple[int, str], float] = {}
COOLDOWN_SECONDS = {
    "intruso": 45,
    "familiar": 120,
    "vehiculo_detenido": 60,
    "vehiculo_bloqueando_salida": 30,
    "permanencia": 60,
    "manipulacion_reja": 30,
    "timbre": 20,
    "panico": 0,  # el pánico nunca tiene cooldown
}

SEVERITY_BY_TYPE = {
    "intruso": "critical",
    "familiar": "info",
    "vehiculo_detenido": "warning",
    "vehiculo_bloqueando_salida": "critical",
    "permanencia": "warning",
    "manipulacion_reja": "critical",
    "timbre": "info",
    "panico": "critical",
}

CAPTIONS = {
    "intruso": "⚠️ *Rostro desconocido detectado* frente a la cámara.",
    "familiar": "✅ Se detectó a *{detail}* (rostro conocido).",
    "vehiculo_detenido": "🚗 *Vehículo detenido* en zona de calle/vereda.",
    "permanencia": "🕐 *Permanencia sospechosa*: alguien parado frente a la reja hace más de {detail}s.",
    "manipulacion_reja": "🚨 *Posible manipulación de la reja* detectada.",
    "timbre": "🔔 *Movimiento en el timbre* — parece que alguien tocó o se acercó a la puerta.",
    "panico": "🆘🆘 *BOTÓN DE PÁNICO ACTIVADO* 🆘🆘",
}


def _cooldown_ok(camera_id: int, alert_type: str) -> bool:
    key = (camera_id, alert_type)
    last = _last_alert_time.get(key, 0)
    cd = COOLDOWN_SECONDS.get(alert_type, 30)
    if time.time() - last < cd:
        return False
    _last_alert_time[key] = time.time()
    return True


def raise_alert(
    user_id: int,
    camera_id: int,
    alert_type: str,
    frame: Optional[np.ndarray] = None,
    zone_id: Optional[int] = None,
    detail: str = "",
    force: bool = False,
    message_override: Optional[str] = None,
) -> Optional[Alert]:
    if not force and not _cooldown_ok(camera_id, alert_type):
        return None

    os.makedirs(settings.SNAPSHOTS_DIR, exist_ok=True)
    image_path = None
    if frame is not None:
        filename = f"{camera_id}_{alert_type}_{uuid.uuid4().hex}.jpg"
        image_path = os.path.join(settings.SNAPSHOTS_DIR, filename)
        cv2.imwrite(image_path, frame)

    if message_override is not None:
        message = message_override
    else:
        caption_template = CAPTIONS.get(alert_type, "Alerta: {detail}")
        message = caption_template.format(detail=detail)

    with Session(engine, expire_on_commit=False) as session:
        alert = Alert(
            user_id=user_id,
            camera_id=camera_id,
            zone_id=zone_id,
            type=alert_type,
            severity=SEVERITY_BY_TYPE.get(alert_type, "info"),
            message=message,
            image_path=image_path,
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)

        tg_config = session.exec(
            select(TelegramConfig).where(TelegramConfig.user_id == user_id)
        ).first()
        if tg_config and tg_config.enabled:
            ok, _detail = enviar_alerta_telegram(
                tg_config.bot_token, tg_config.chat_id, image_path, message
            )
            alert.telegram_sent = ok
            session.add(alert)
            session.commit()

        return alert
