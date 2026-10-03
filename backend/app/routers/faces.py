import base64
import json
import os
import uuid

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.auth import get_current_user
from app.config import settings
from app.database import get_session
from app.models import Camera, KnownFace, User
from app.schemas import KnownFaceOut
from app.vision import camera_worker, face_engine
from app.vision.rtsp_utils import test_rtsp_connection

router = APIRouter(prefix="/api/faces", tags=["faces"])


def _save_face_from_bytes(session: Session, user_id: int, name: str, content: bytes) -> KnownFace:
    """Lógica compartida: guarda la foto en disco, detecta la cara más grande,
    calcula su embedding y crea el KnownFace. La usan tanto la subida de archivo
    como la captura directa desde una cámara."""
    if not face_engine.models_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Los modelos de reconocimiento facial todavía no están descargados. "
                "Corré backend/scripts/download_models.sh primero."
            ),
        )

    img_array = np.frombuffer(content, dtype=np.uint8)
    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="No se pudo leer la imagen.")

    faces = face_engine.detect_faces(frame)
    if not faces:
        raise HTTPException(
            status_code=400,
            detail="No se detectó ningún rostro en la foto. Probá con otra imagen más clara y de frente.",
        )
    # Tomamos la cara más grande de la foto (debería ser la única / la principal)
    faces_sorted = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    embedding = face_engine.get_embedding(frame, faces_sorted[0])
    embedding_json = json.dumps(embedding.flatten().tolist())

    os.makedirs(settings.FACES_DIR, exist_ok=True)
    filename = f"{user_id}_{uuid.uuid4().hex}.jpg"
    path = os.path.join(settings.FACES_DIR, filename)
    with open(path, "wb") as f:
        f.write(content)

    face = KnownFace(user_id=user_id, name=name, image_path=path, embedding_json=embedding_json)
    session.add(face)
    session.commit()
    session.refresh(face)
    # Si ya tenés una cámara monitoreando, que se entere de esta cara nueva ya mismo
    # (si no, seguía comparando contra la lista vieja hasta reiniciar el monitoreo).
    camera_worker.reload_known_faces(user_id)
    return face


@router.get("", response_model=list[KnownFaceOut])
def list_faces(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    faces = session.exec(select(KnownFace).where(KnownFace.user_id == current_user.id)).all()
    return faces


@router.post("", response_model=KnownFaceOut)
async def upload_face(
    name: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    return _save_face_from_bytes(session, current_user.id, name, content)


@router.post("/from-camera", response_model=KnownFaceOut)
def add_face_from_camera(
    camera_id: int,
    name: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Enrola una cara agarrando una foto fresca directamente de la cámara, en vez de
    una selfie del celular. Esto es mucho más confiable: la luz, el ángulo y la
    distancia terminan siendo exactamente los mismos que la cámara va a ver después
    en vivo, que es justo lo que puede fallar con una selfie bien iluminada de frente."""
    cam = session.get(Camera, camera_id)
    if not cam or cam.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    result = test_rtsp_connection(cam.rtsp_url)
    if not result.ok or not result.snapshot_base64:
        raise HTTPException(
            status_code=400,
            detail=result.message or "No se pudo tomar una foto de esta cámara ahora mismo.",
        )
    content = base64.b64decode(result.snapshot_base64)
    return _save_face_from_bytes(session, current_user.id, name, content)


@router.delete("/{face_id}")
def delete_face(
    face_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    face = session.get(KnownFace, face_id)
    if not face or face.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rostro no encontrado")
    if os.path.exists(face.image_path):
        os.remove(face.image_path)
    user_id = face.user_id
    session.delete(face)
    session.commit()
    camera_worker.reload_known_faces(user_id)
    return {"ok": True}
