from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.models import Camera, User
from app.schemas import CameraCreate, CameraOut, CameraTestResult, CameraUpdate
from app.vision.rtsp_utils import BRAND_URL_TEMPLATES, test_rtsp_connection
from app.vision import camera_worker

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("/brands")
def list_brands():
    """Marcas/familias soportadas para precargar la plantilla de URL RTSP en el wizard."""
    return {"brands": list(BRAND_URL_TEMPLATES.keys())}


@router.post("/test-connection", response_model=CameraTestResult)
def test_connection(payload: dict, current_user: User = Depends(get_current_user)):
    rtsp_url = payload.get("rtsp_url")
    if not rtsp_url:
        raise HTTPException(status_code=400, detail="Falta rtsp_url")
    result = test_rtsp_connection(rtsp_url)
    return CameraTestResult(**result.__dict__)


@router.get("", response_model=list[CameraOut])
def list_cameras(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    cams = session.exec(select(Camera).where(Camera.user_id == current_user.id)).all()
    return cams


@router.post("", response_model=CameraOut)
def create_camera(
    data: CameraCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    cam = Camera(user_id=current_user.id, name=data.name, brand=data.brand, rtsp_url=data.rtsp_url)
    session.add(cam)
    session.commit()
    session.refresh(cam)
    return cam


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(
    camera_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    cam = session.get(Camera, camera_id)
    if not cam or cam.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    return cam


@router.put("/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: int,
    data: CameraUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    cam = session.get(Camera, camera_id)
    if not cam or cam.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    if data.name is not None:
        cam.name = data.name
    if data.brand is not None:
        cam.brand = data.brand
    if data.rtsp_url is not None and data.rtsp_url != cam.rtsp_url:
        cam.rtsp_url = data.rtsp_url
        was_monitoring = cam.is_monitoring
        if was_monitoring:
            # Si cambió la URL hay que reiniciar el worker para que tome el nuevo stream.
            camera_worker.stop_worker(camera_id)
    session.add(cam)
    session.commit()
    session.refresh(cam)
    if data.rtsp_url is not None and cam.is_monitoring:
        camera_worker.start_worker(camera_id)
    return cam


@router.get("/{camera_id}/snapshot", response_model=CameraTestResult)
def camera_snapshot(
    camera_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Foto fresca (sin overlays) de la cámara, para dibujar zonas nuevas desde la
    pantalla de configuración de una cámara ya existente."""
    cam = session.get(Camera, camera_id)
    if not cam or cam.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    result = test_rtsp_connection(cam.rtsp_url)
    return CameraTestResult(**result.__dict__)


@router.delete("/{camera_id}")
def delete_camera(
    camera_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    cam = session.get(Camera, camera_id)
    if not cam or cam.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    camera_worker.stop_worker(camera_id)
    session.delete(cam)
    session.commit()
    return {"ok": True}


@router.post("/{camera_id}/start")
def start_monitoring(
    camera_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    cam = session.get(Camera, camera_id)
    if not cam or cam.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    cam.is_monitoring = True
    session.add(cam)
    session.commit()
    camera_worker.start_worker(camera_id)
    return {"ok": True}


@router.post("/{camera_id}/stop")
def stop_monitoring(
    camera_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    cam = session.get(Camera, camera_id)
    if not cam or cam.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    cam.is_monitoring = False
    session.add(cam)
    session.commit()
    camera_worker.stop_worker(camera_id)
    return {"ok": True}
