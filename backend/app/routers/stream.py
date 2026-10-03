import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.auth import get_current_user_from_query_or_header
from app.database import get_session
from app.models import Camera, User
from app.vision import camera_worker

router = APIRouter(prefix="/api/stream", tags=["stream"])

PLACEHOLDER_JPEG = None  # se genera una vez, ver abajo


def _blank_frame_jpeg() -> bytes:
    global PLACEHOLDER_JPEG
    if PLACEHOLDER_JPEG is None:
        import cv2
        import numpy as np

        img = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(
            img, "Esperando video...", (120, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 2
        )
        ok, buf = cv2.imencode(".jpg", img)
        PLACEHOLDER_JPEG = buf.tobytes() if ok else b""
    return PLACEHOLDER_JPEG


def _mjpeg_generator(camera_id: int):
    boundary = b"--frame"
    while True:
        jpeg = camera_worker.get_latest_jpeg(camera_id) or _blank_frame_jpeg()
        yield (
            boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        )
        time.sleep(0.08)  # ~12 fps hacia el navegador, de sobra para un dashboard


@router.get("/{camera_id}")
def stream_camera(
    camera_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user_from_query_or_header),
):
    cam = session.get(Camera, camera_id)
    if not cam or cam.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    return StreamingResponse(
        _mjpeg_generator(camera_id), media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/{camera_id}/status")
def stream_status(
    camera_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user_from_query_or_header),
):
    cam = session.get(Camera, camera_id)
    if not cam or cam.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    return {"db_status": cam.status, "worker_status": camera_worker.get_status(camera_id)}
