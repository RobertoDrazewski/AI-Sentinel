from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.auth import get_current_user
from app.config import settings
from app.database import get_session
from app.integrations.mercadopago_client import create_subscription_preference, get_sdk
from app.models import Subscription, User
from app.schemas import SubscriptionOut

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


def _get_or_create(session: Session, user_id: int) -> Subscription:
    sub = session.exec(select(Subscription).where(Subscription.user_id == user_id)).first()
    if not sub:
        sub = Subscription(user_id=user_id, amount_ars=settings.MP_PLAN_PRICE_ARS)
        session.add(sub)
        session.commit()
        session.refresh(sub)
    return sub


@router.get("", response_model=SubscriptionOut)
def get_subscription(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return _get_or_create(session, current_user.id)


@router.post("/create-preference")
def create_preference(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if not settings.MP_ACCESS_TOKEN:
        return {
            "ok": False,
            "message": "Falta configurar MP_ACCESS_TOKEN en el .env del backend (usá tus credenciales de TEST).",
        }
    pref = create_subscription_preference(current_user.email, current_user.id)
    sub = _get_or_create(session, current_user.id)
    sub.mp_preference_id = pref.get("id")
    session.add(sub)
    session.commit()
    return {
        "ok": True,
        "preference_id": pref.get("id"),
        "init_point": pref.get("init_point"),
        "sandbox_init_point": pref.get("sandbox_init_point"),
    }


@router.post("/webhook")
async def mp_webhook(request: Request, session: Session = Depends(get_session)):
    """Mercado Pago pega acá cuando cambia el estado de un pago. En localhost esto
    sólo lo vas a poder probar con un túnel público (ngrok/cloudflared) apuntando
    a este backend, o simulando manualmente con /simulate-payment más abajo."""
    body = await request.json()
    payment_id = body.get("data", {}).get("id") or request.query_params.get("id")
    if not payment_id:
        return {"ok": True}  # notificación que no trae id, la ignoramos

    sdk = get_sdk()
    payment_info = sdk.payment().get(payment_id)["response"]
    external_reference = payment_info.get("external_reference")
    status_mp = payment_info.get("status")  # approved | pending | rejected | ...

    if external_reference:
        sub = session.exec(
            select(Subscription).where(Subscription.user_id == int(external_reference))
        ).first()
        if sub:
            sub.mp_payment_id = str(payment_id)
            sub.status = "activa" if status_mp == "approved" else "pendiente"
            session.add(sub)
            session.commit()

    return {"ok": True}


@router.post("/simulate-payment")
def simulate_payment(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """SOLO PARA DESARROLLO LOCAL: activa la suscripción sin pasar por Mercado Pago,
    para poder probar el resto del sistema sin depender de un túnel público.
    Sacar o proteger este endpoint antes de llevar esto a producción."""
    sub = _get_or_create(session, current_user.id)
    sub.status = "activa"
    session.add(sub)
    session.commit()
    return {"ok": True, "status": sub.status}
