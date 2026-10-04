from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.models import Alert, AgentToken, Camera, Payment, Subscription, User
from app.schemas import AdminUserSummary, AgentDeviceOut, SubscriptionStatusUpdate
from app.utils import add_one_month

router = APIRouter(prefix="/api/admin", tags=["admin"])

_VALID_STATUSES = {"pendiente", "activa", "vencida", "cancelada"}


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Sólo el/los usuario(s) con role=admin de esta instalación (el dueño, quien la
    instaló) puede ver o tocar la pestaña Admin. Cualquier otro usuario logueado recibe
    403, igual que si no existiera el endpoint."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Sólo un administrador puede ver esto")
    return current_user


@router.get("/users", response_model=list[AdminUserSummary])
def list_users(session: Session = Depends(get_session), _: User = Depends(require_admin)):
    """Control de cuentas y suscripciones: un vistazo de cada usuario de esta
    instalación -- su plan, cuándo le vence, cuántas cámaras tiene y si el sistema le
    generó alertas este mes -- para llevar el control sin entrar cuenta por cuenta."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    users = session.exec(select(User).order_by(User.created_at)).all()
    out: list[AdminUserSummary] = []
    for u in users:
        sub = session.exec(select(Subscription).where(Subscription.user_id == u.id)).first()
        last_payment = session.exec(
            select(Payment).where(Payment.user_id == u.id).order_by(Payment.paid_at.desc())
        ).first()
        next_due = add_one_month(last_payment.paid_at) if last_payment else None
        cameras_count = len(session.exec(select(Camera).where(Camera.user_id == u.id)).all())
        alerts_count = len(
            session.exec(
                select(Alert).where(Alert.user_id == u.id).where(Alert.created_at >= month_start)
            ).all()
        )
        devices_count = len(
            session.exec(select(AgentToken).where(AgentToken.user_id == u.id)).all()
        )
        out.append(
            AdminUserSummary(
                id=u.id,
                email=u.email,
                business_name=u.business_name,
                role=u.role,
                created_at=u.created_at,
                subscription_status=sub.status if sub else "sin_suscripcion",
                amount_ars=sub.amount_ars if sub else 0,
                next_due_date=next_due,
                cameras_count=cameras_count,
                alerts_this_month=alerts_count,
                devices_count=devices_count,
            )
        )
    return out


@router.get("/users/{user_id}/devices", response_model=list[AgentDeviceOut])
def list_user_devices(
    user_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    """Qué PCs tiene emparejadas esta cuenta -- para revisar algo raro (ej: dos
    dispositivos activos el mismo día desde IPs muy distintas) antes de decidir
    si conviene revocar uno."""
    rows = session.exec(select(AgentToken).where(AgentToken.user_id == user_id)).all()
    return [
        AgentDeviceOut(
            id=r.id,
            label=r.label,
            created_at=r.created_at,
            last_seen_at=r.last_seen_at,
            last_seen_ip=r.last_seen_ip,
        )
        for r in rows
    ]


@router.delete("/users/{user_id}/devices/{device_id}")
def revoke_user_device(
    user_id: int,
    device_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    """Revoca a mano el agente de un cliente (ej: parece compartido, se vendió la
    PC, o directamente se le quiere cortar el acceso) -- el ejecutable de esa PC
    deja de poder validar la licencia en la próxima consulta."""
    row = session.get(AgentToken, device_id)
    if not row or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="No encontrado")
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.put("/users/{user_id}/subscription-status")
def set_subscription_status(
    user_id: int,
    data: SubscriptionStatusUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    """Para marcar a mano el estado de una suscripción -- ej: el cliente te pagó por
    transferencia en vez de Mercado Pago, o se la querés vencer/cancelar manualmente."""
    if data.status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Estado inválido")
    sub = session.exec(select(Subscription).where(Subscription.user_id == user_id)).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Ese usuario todavía no tiene suscripción")
    sub.status = data.status
    session.add(sub)
    session.commit()
    return {"ok": True, "status": sub.status}
