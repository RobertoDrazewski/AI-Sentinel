"""Suscripción mensual vía Mercado Pago (Checkout Pro).

Para producción se usaría una "preapproval" (suscripción recurrente real) de MP.
Para este prototipo local armamos lo más simple que se puede probar ya: una
preferencia de pago (Checkout Pro) por el monto del plan, más un endpoint de
webhook para que MP te avise cuando se acredita el pago.

IMPORTANTE para probar en localhost: Mercado Pago necesita una URL pública para
mandar el webhook (no le puede pegar a localhost). Para probarlo end-to-end local
hace falta un túnel tipo ngrok/cloudflared apuntando al puerto 8000, o usar el
endpoint /api/subscription/simulate-payment (dev-only) para simular la activación
sin depender de MP durante el desarrollo.
"""
from __future__ import annotations

import mercadopago

from app.config import settings


def get_sdk() -> mercadopago.SDK:
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)


def create_subscription_preference(user_email: str, user_id: int) -> dict:
    sdk = get_sdk()
    preference_data = {
        "items": [
            {
                "title": "AI Sentinel - Suscripción mensual",
                "quantity": 1,
                "unit_price": float(settings.MP_PLAN_PRICE_ARS),
                "currency_id": "ARS",
            }
        ],
        "payer": {"email": user_email},
        "back_urls": {
            "success": f"{settings.FRONTEND_ORIGIN}/billing?status=success",
            "failure": f"{settings.FRONTEND_ORIGIN}/billing?status=failure",
            "pending": f"{settings.FRONTEND_ORIGIN}/billing?status=pending",
        },
        "auto_return": "approved",
        "notification_url": settings.MP_WEBHOOK_URL,
        "external_reference": str(user_id),
    }
    result = sdk.preference().create(preference_data)
    return result["response"]
