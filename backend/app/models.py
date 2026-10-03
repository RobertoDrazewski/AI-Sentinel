from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    business_name: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    plan_status: str = Field(default="trial")  # trial | active | past_due | cancelled


class Camera(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str
    brand: str = Field(default="generico")  # ezviz_hikvision | dahua | reolink | onvif_generico | otro
    rtsp_url: str
    status: str = Field(default="desconectada")  # desconectada | conectada | error
    is_monitoring: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)


class Zone(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    camera_id: int = Field(foreign_key="camera.id", index=True)
    name: str
    kind: str = Field(default="custom")  # reja | calle | custom
    # Polígono en coordenadas relativas 0-1 (x,y) para que sea independiente de la resolución.
    # Se guarda como JSON string: "[[x1,y1],[x2,y2],...]"
    polygon_json: str
    loiter_seconds: int = Field(default=5)
    detect_vehicles: bool = Field(default=False)
    detect_people: bool = Field(default=True)
    detect_gate_tamper: bool = Field(default=False)
    # Cuántos segundos tiene que estar detenido un vehículo en esta zona para avisar
    # (ej: 60 = "si se queda parqueado más de 1 minuto"). Antes era un valor fijo de
    # 8s para todas las zonas; ahora es por zona.
    vehicle_stop_seconds: int = Field(default=60)
    # Marca esta zona como "tapa mi salida" (ej: el triángulo frente al garage). Un
    # vehículo detenido ahí dispara una alarma roja/crítica en vez de un aviso normal.
    blocks_exit: bool = Field(default=False)


class KnownFace(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str
    image_path: str
    embedding_json: Optional[str] = None  # vector SFace (128 floats) como JSON
    created_at: datetime = Field(default_factory=utcnow)


class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    camera_id: int = Field(foreign_key="camera.id", index=True)
    zone_id: Optional[int] = Field(default=None, foreign_key="zone.id")
    type: str  # intruso | familiar | vehiculo_detenido | permanencia | manipulacion_reja | panico
    severity: str = Field(default="info")  # info | warning | critical
    message: str
    image_path: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    telegram_sent: bool = Field(default=False)


class TelegramConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    bot_token: str
    chat_id: str
    enabled: bool = Field(default=True)


class PanicContact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    phone_number: str  # formato E.164, ej: +5492615551234
    notes: Optional[str] = None


class Subscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    mp_preference_id: Optional[str] = None
    mp_payment_id: Optional[str] = None
    status: str = Field(default="pendiente")  # pendiente | activa | vencida | cancelada
    amount_ars: float = Field(default=30000)
    updated_at: datetime = Field(default_factory=utcnow)
