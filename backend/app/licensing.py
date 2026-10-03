from datetime import datetime, timezone
from typing import Optional

from app.models import Subscription, User


def compute_license_status(user: User, subscription: Optional[Subscription]) -> dict:
    """Decide si el agente local de este usuario puede usar la parte "inteligente"
    (reconocimiento facial, detección de zonas, alertas) o si tiene que quedar
    funcionando sólo como visor de cámara en vivo, sin IA.

    Reglas (en este orden):
    1. El admin de la instalación (vos) nunca queda bloqueado -- es tu propia
       instalación, no tiene sentido cortarte el servicio a vos mismo.
    2. Si la prueba gratis de 30 días sigue vigente, IA habilitada.
    3. Si la suscripción está "activa" (pagó), IA habilitada.
    4. Cualquier otro caso (prueba vencida y no pagó, o suscripción "vencida" /
       "cancelada" / "pendiente") -> IA deshabilitada, pero la cámara en vivo
       y la app en sí siguen funcionando normalmente.
    """
    now = datetime.now(timezone.utc)

    if user.role == "admin":
        return {
            "ai_enabled": True,
            "status": "admin",
            "reason": "Cuenta administradora de esta instalación",
            "trial_ends_at": user.trial_ends_at,
            "trial_active": True,
        }

    trial_ends_at = user.trial_ends_at
    trial_active = trial_ends_at is not None and now < trial_ends_at

    if trial_active:
        return {
            "ai_enabled": True,
            "status": "trial",
            "reason": "Prueba gratis de 30 días vigente",
            "trial_ends_at": trial_ends_at,
            "trial_active": True,
        }

    sub_status = subscription.status if subscription else "pendiente"
    if sub_status == "activa":
        return {
            "ai_enabled": True,
            "status": "activa",
            "reason": "Suscripción al día",
            "trial_ends_at": trial_ends_at,
            "trial_active": False,
        }

    return {
        "ai_enabled": False,
        "status": sub_status,
        "reason": "Prueba vencida y sin suscripción activa",
        "trial_ends_at": trial_ends_at,
        "trial_active": False,
    }
