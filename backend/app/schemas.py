from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


# --- Auth ---
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    business_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    business_name: Optional[str] = None
    plan_status: str


# --- Cameras ---
class CameraCreate(BaseModel):
    name: str
    brand: str = "generico"
    rtsp_url: str


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    rtsp_url: Optional[str] = None


class CameraOut(BaseModel):
    id: int
    name: str
    brand: str
    rtsp_url: str
    status: str
    is_monitoring: bool


class CameraTestResult(BaseModel):
    ok: bool
    message: str
    width: Optional[int] = None
    height: Optional[int] = None
    snapshot_base64: Optional[str] = None


# --- Zones ---
class Point(BaseModel):
    x: float
    y: float


class ZoneCreate(BaseModel):
    camera_id: int
    name: str
    kind: str = "custom"
    polygon: List[Point]
    loiter_seconds: int = 5
    detect_vehicles: bool = False
    detect_people: bool = True
    detect_gate_tamper: bool = False
    vehicle_stop_seconds: int = 60
    blocks_exit: bool = False


class ZoneUpdate(BaseModel):
    loiter_seconds: Optional[int] = None
    detect_vehicles: Optional[bool] = None
    detect_people: Optional[bool] = None
    detect_gate_tamper: Optional[bool] = None
    vehicle_stop_seconds: Optional[int] = None
    blocks_exit: Optional[bool] = None


class ZoneOut(BaseModel):
    id: int
    camera_id: int
    name: str
    kind: str
    polygon: List[Point]
    loiter_seconds: int
    detect_vehicles: bool
    detect_people: bool
    detect_gate_tamper: bool
    vehicle_stop_seconds: int
    blocks_exit: bool


# --- Faces ---
class KnownFaceOut(BaseModel):
    id: int
    name: str
    image_path: str


# --- Alerts ---
class AlertOut(BaseModel):
    id: int
    camera_id: int
    zone_id: Optional[int]
    type: str
    severity: str
    message: str
    image_path: Optional[str]
    created_at: datetime
    telegram_sent: bool


# --- Telegram ---
class TelegramConfigIn(BaseModel):
    bot_token: str
    chat_id: str
    enabled: bool = True


class TelegramConfigOut(BaseModel):
    bot_token: str
    chat_id: str
    enabled: bool


# --- Panic ---
class PanicContactIn(BaseModel):
    phone_number: str
    notes: Optional[str] = None


# --- Subscription ---
class SubscriptionOut(BaseModel):
    status: str
    amount_ars: float
    mp_preference_id: Optional[str] = None
