"""Envío de alertas por Telegram. Basado en el script que ya veníamos usando,
pero parametrizado por usuario (cada usuario configura su propio bot_token/chat_id
desde la app en vez de tenerlo hardcodeado)."""
from __future__ import annotations

import requests


def enviar_alerta_telegram(
    token_bot: str, chat_id: str, image_path: str | None, caption_text: str
) -> tuple[bool, str]:
    """Envía una foto (si hay) + texto a un chat de Telegram. Devuelve (ok, detalle)."""
    if not token_bot or not chat_id:
        return False, "Falta configurar el bot de Telegram (token o chat_id)."

    try:
        if image_path:
            url = f"https://api.telegram.org/bot{token_bot}/sendPhoto"
            with open(image_path, "rb") as photo_file:
                files = {"photo": photo_file}
                data = {"chat_id": chat_id, "caption": caption_text, "parse_mode": "Markdown"}
                response = requests.post(url, data=data, files=files, timeout=10)
        else:
            url = f"https://api.telegram.org/bot{token_bot}/sendMessage"
            data = {"chat_id": chat_id, "text": caption_text, "parse_mode": "Markdown"}
            response = requests.post(url, data=data, timeout=10)

        if response.status_code == 200:
            return True, "Alerta de Telegram enviada exitosamente."
        return False, f"Error al enviar alerta a Telegram: {response.text}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Excepción en conexión con Telegram: {exc}"
