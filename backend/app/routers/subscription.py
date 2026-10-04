from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.auth import get_current_user
from app.config import settings
from app.database import get_session
from app.integrations.mercadopago_client import create_subscription_preference, get_sdk
from app.models import Alert, Payment, Subscription, User
from app.schemas import AccountSummaryOut, PaymentOut, SubscriptionOut
from app.utils import add_one_month

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


def _get_or_create(session: Session, user_id: int) -> Subscription:
    sub = session.exec(select(Subscription).where(Subscription.user_id == user_id)).first()
    if not sub:
        sub = Subscription(user_id=user_id, amount_ars=settings.MP_PLAN_PRICE_ARS)
        session.add(sub)
        session.commit()
        session.refresh(sub)
    return sub


def _record_payment(session: Session, user_id: int, amount_ars: float, mp_payment_id: str | None) -> None:
    """Guarda un pago en el historial, salvo que ya lo hayamos registrado antes (Mercado
    Pago puede reenviar el mismo webhook más de una vez)."""
    if mp_payment_id:
        existing = session.exec(
            select(Payment).where(Payment.mp_payment_id == mp_payment_id)
        ).first()
        if existing:
            return
    session.add(Payment(user_id=user_id, amount_ars=amount_ars, mp_payment_id=mp_payment_id, status="aprobado"))
    session.commit()


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
            if status_mp == "approved":
                amount = payment_info.get("transaction_amount") or sub.amount_ars
                _record_payment(session, sub.user_id, amount, str(payment_id))

    return {"ok": True}


@router.post("/simulate-payment")
def simulate_payment(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """SOLO PARA DESARROLLO LOCAL: activa la suscripción sin pasar por Mercado Pago,
    para poder probar el resto del sistema sin depender de un túnel público.
    Apagado por defecto (ver ALLOW_SIMULATED_PAYMENTS en config.py) -- en el
    servidor de producción esto tiene que seguir apagado siempre."""
    if not settings.ALLOW_SIMULATED_PAYMENTS:
        raise HTTPException(
            status_code=403,
            detail="Simular pagos está deshabilitado en este servidor.",
        )
    sub = _get_or_create(session, current_user.id)
    sub.status = "activa"
    session.add(sub)
    session.commit()
    _record_payment(session, current_user.id, sub.amount_ars, None)
    return {"ok": True, "status": sub.status}


@router.get("/summary", response_model=AccountSummaryOut)
def get_account_summary(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """Para la pantalla "Mi cuenta": estado de la suscripción, los pagos de este mes,
    cuándo vence la próxima cuota, y un resumen de uso del mes (caras reconocidas,
    alertas críticas) para que el cliente vea que lo que paga se está usando."""
    sub = _get_or_create(session, current_user.id)

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    payments_this_month = session.exec(
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .where(Payment.paid_at >= month_start)
        .order_by(Payment.paid_at.desc())
    ).all()

    last_payment = session.exec(
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.paid_at.desc())
    ).first()
    next_due_date = add_one_month(last_payment.paid_at) if last_payment else None

    alerts_query = select(Alert).where(Alert.user_id == current_user.id).where(
        Alert.created_at >= month_start
    )
    alerts_this_month = session.exec(alerts_query).all()
    faces_recognized = sum(1 for a in alerts_this_month if a.type == "familiar")
    critical_alerts = sum(1 for a in alerts_this_month if a.severity == "critical")

    return AccountSummaryOut(
        subscription=SubscriptionOut(
            status=sub.status, amount_ars=sub.amount_ars, mp_preference_id=sub.mp_preference_id
        ),
        next_due_date=next_due_date,
        payments_this_month=[
            PaymentOut(amount_ars=p.amount_ars, status=p.status, paid_at=p.paid_at)
            for p in payments_this_month
        ],
        faces_recognized_this_month=faces_recognized,
        critical_alerts_this_month=critical_alerts,
        total_alerts_this_month=len(alerts_this_month),
    )
