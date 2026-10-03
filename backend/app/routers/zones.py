import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.models import Camera, User, Zone
from app.schemas import Point, ZoneCreate, ZoneOut, ZoneUpdate

router = APIRouter(prefix="/api/zones", tags=["zones"])


def _zone_to_out(zone: Zone) -> ZoneOut:
    points = [Point(x=p[0], y=p[1]) for p in json.loads(zone.polygon_json)]
    return ZoneOut(
        id=zone.id,
        camera_id=zone.camera_id,
        name=zone.name,
        kind=zone.kind,
        polygon=points,
        loiter_seconds=zone.loiter_seconds,
        detect_vehicles=zone.detect_vehicles,
        detect_people=zone.detect_people,
        detect_gate_tamper=zone.detect_gate_tamper,
        vehicle_stop_seconds=zone.vehicle_stop_seconds,
        blocks_exit=zone.blocks_exit,
    )


def _assert_camera_owned(session: Session, camera_id: int, user: User) -> Camera:
    cam = session.get(Camera, camera_id)
    if not cam or cam.user_id != user.id:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    return cam


@router.get("/by-camera/{camera_id}", response_model=list[ZoneOut])
def list_zones(
    camera_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _assert_camera_owned(session, camera_id, current_user)
    zones = session.exec(select(Zone).where(Zone.camera_id == camera_id)).all()
    return [_zone_to_out(z) for z in zones]


@router.post("", response_model=ZoneOut)
def create_zone(
    data: ZoneCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _assert_camera_owned(session, data.camera_id, current_user)
    zone = Zone(
        camera_id=data.camera_id,
        name=data.name,
        kind=data.kind,
        polygon_json=json.dumps([[p.x, p.y] for p in data.polygon]),
        loiter_seconds=data.loiter_seconds,
        detect_vehicles=data.detect_vehicles,
        detect_people=data.detect_people,
        detect_gate_tamper=data.detect_gate_tamper,
        vehicle_stop_seconds=data.vehicle_stop_seconds,
        blocks_exit=data.blocks_exit,
    )
    session.add(zone)
    session.commit()
    session.refresh(zone)
    return _zone_to_out(zone)


@router.put("/{zone_id}", response_model=ZoneOut)
def update_zone(
    zone_id: int,
    data: ZoneUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    zone = session.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    _assert_camera_owned(session, zone.camera_id, current_user)
    for field_name in (
        "name",
        "loiter_seconds",
        "detect_vehicles",
        "detect_people",
        "detect_gate_tamper",
        "vehicle_stop_seconds",
        "blocks_exit",
    ):
        value = getattr(data, field_name)
        if value is not None:
            setattr(zone, field_name, value)
    session.add(zone)
    session.commit()
    session.refresh(zone)
    return _zone_to_out(zone)


@router.delete("/{zone_id}")
def delete_zone(
    zone_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    zone = session.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    _assert_camera_owned(session, zone.camera_id, current_user)
    session.delete(zone)
    session.commit()
    return {"ok": True}
