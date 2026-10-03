from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.licensing import compute_license_status
from app.models import AgentToken, Subscription, User
from app.schemas import AgentDeviceOut, AgentPairIn, AgentPairOut, LicenseStatusOut

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/pair", response_model=AgentPairOut)
def pair_agent(
    data: AgentPairIn,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """El agente local llama acá UNA sola vez, recién instalado, usando el JWT que
    obtuvo al loguearse con el email/contraseña de la cuenta (igual que el panel
    web). A cambio le damos un token de larga duración que guarda en disco y usa
    de ahí en más -- así la contraseña nunca queda guardada en la PC del cliente."""
    token_row = AgentToken(user_id=current_user.id, label=data.label or "Agente")
    session.add(token_row)
    session.commit()
    session.refresh(token_row)
    return AgentPairOut(token=token_row.token, label=token_row.label, device_id=token_row.id)


@router.get("/devices", response_model=list[AgentDeviceOut])
def list_devices(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """Para la pantalla "Mi cuenta": qué agentes (PCs) están emparejados con esta
    cuenta, para poder revocar uno si hace falta (se vendió la PC, etc.)."""
    rows = session.exec(
        select(AgentToken).where(AgentToken.user_id == current_user.id)
    ).all()
    return [
        AgentDeviceOut(id=r.id, label=r.label, created_at=r.created_at, last_seen_at=r.last_seen_at)
        for r in rows
    ]


@router.delete("/devices/{device_id}")
def revoke_device(
    device_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    row = session.get(AgentToken, device_id)
    if not row or row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="No encontrado")
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.get("/license", response_model=LicenseStatusOut)
def license_status(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """El agente local (y el panel web) consultan esto para saber si la parte
    inteligente (reconocimiento facial, detección de zonas, alertas) tiene que
    estar prendida o apagada en este momento. Pensado para que el agente lo
    chequee al arrancar y después cada 1 hora o así -- no hace falta más
    frecuencia que esa."""
    sub = session.exec(
        select(Subscription).where(Subscription.user_id == current_user.id)
    ).first()
    return LicenseStatusOut(**compute_license_status(current_user, sub))
