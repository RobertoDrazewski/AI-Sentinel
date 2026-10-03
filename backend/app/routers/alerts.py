import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.models import Alert, Camera, PanicContact, User
from app.schemas import AlertOut, PanicContactIn
from app.vision.alert_manager import raise_alert
from app.vision.camera_worker import get_latest_jpeg

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    camera_id: int | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    query = select(Alert).where(Alert.user_id == current_user.id)
    if camera_id:
        query = query.where(Alert.camera_id == camera_id)
    query = query.order_by(Alert.created_at.desc()).limit(limit)
    return session.exec(query).all()


@router.get("/alerts/{alert_id}/image")
def alert_image(
    alert_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    alert = session.get(Alert, alert_id)
    if not alert or alert.user_id != current_user.id or not alert.image_path:
        raise HTTPException(status_code=404, detail="No hay imagen para esta alerta")
    if not os.path.exists(alert.image_path):
        raise HTTPException(status_code=404, detail="La imagen ya no está disponible")
    return FileResponse(alert.image_path)


@router.post("/panic/{camera_id}")
def trigger_panic(
    camera_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Botón de pánico. Dispara una alerta crítica (Telegram + queda registrada) con
    máxima prioridad y sin cooldown. La app, del lado del navegador/celular, es la
    que además abre el marcador con tel:911 (ver PanicButton en el frontend):
    no existe ninguna API para marcar al 911 de forma 100% automática y sin
    intervención humana, así que el flujo es "un toque: alerta + abrir llamada"."""
    cam = session.get(Camera, camera_id)
    if not cam or cam.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    frame_jpeg = get_latest_jpeg(camera_id)
    frame = None
    if frame_jpeg:
        import cv2
        import numpy as np

        frame = cv2.imdecode(np.frombuffer(frame_jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)

    alert = raise_alert(current_user.id, camera_id, "panico", frame, force=True)

    contact = session.exec(
        select(PanicContact).where(PanicContact.user_id == current_user.id)
    ).first()

    return {
        "ok": True,
        "alert_id": alert.id if alert else None,
        "panic_contact": contact.phone_number if contact else None,
    }


@router.get("/panic-contact")
def get_panic_contact(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    contact = session.exec(
        select(PanicContact).where(PanicContact.user_id == current_user.id)
    ).first()
    if not contact:
        return {"phone_number": None, "notes": None}
    return {"phone_number": contact.phone_number, "notes": contact.notes}


@router.put("/panic-contact")
def set_panic_contact(
    data: PanicContactIn,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    contact = session.exec(
        select(PanicContact).where(PanicContact.user_id == current_user.id)
    ).first()
    if contact:
        contact.phone_number = data.phone_number
        contact.notes = data.notes
    else:
        contact = PanicContact(
            user_id=current_user.id, phone_number=data.phone_number, notes=data.notes
        )
    session.add(contact)
    session.commit()
    return {"ok": True}
