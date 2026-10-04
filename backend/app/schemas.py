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
    role: str = "cliente"
    trial_ends_at: Optional[datetime] = None


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
    name: Optional[str] = None
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


class PaymentOut(BaseModel):
    amount_ars: float
    status: str
    paid_at: datetime


class AccountSummaryOut(BaseModel):
    """Lo que el cliente ve en "Mi cuenta": su suscripción, el historial de pagos del
    mes y un resumen de uso del mes (cuántas caras reconoció, si hubo alertas críticas)
    para que quede claro el valor de lo que está pagando."""

    subscription: SubscriptionOut
    next_due_date: Optional[datetime] = None
    payments_this_month: List[PaymentOut]
    faces_recognized_this_month: int
    critical_alerts_this_month: int
    total_alerts_this_month: int


# --- Admin ---
class AdminUserSummary(BaseModel):
    """Una fila de la pestaña "Admin": un vistazo de cada cuenta de esta instalación
    (quién es, cómo está su suscripción, cuándo le vence, y si está usando el
    sistema) para que Roberto pueda llevar el control sin entrar cuenta por cuenta."""

    id: int
    email: str
    business_name: Optional[str] = None
    role: str
    created_at: datetime
    subscription_status: str
    amount_ars: float
    next_due_date: Optional[datetime] = None
    cameras_count: int
    alerts_this_month: int
    devices_count: int


class SubscriptionStatusUpdate(BaseModel):
    status: str  # pendiente | activa | vencida | cancelada


# --- Agente local / licencia ---
class AgentPairIn(BaseModel):
    label: Optional[str] = None  # ej: "Mac de Roberto" -- nombre de la máquina
    # Hash de la huella de hardware de la máquina (ver app/device_id.py) -- sirve
    # para notar si esta PC física ya usó el trial gratis con otra cuenta antes.
    # Opcional porque versiones viejas del agente todavía no lo mandan.
    device_fingerprint: Optional[str] = None


class AgentPairOut(BaseModel):
    """Se devuelve UNA sola vez, en el momento del pairing -- el agente la tiene
    que guardar ahí mismo, porque después no se puede volver a consultar (sólo
    mostramos la lista de dispositivos sin el token, por seguridad)."""

    token: str
    label: str
    device_id: int


class AgentDeviceOut(BaseModel):
    id: int
    label: str
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    last_seen_ip: Optional[str] = None


class LicenseStatusOut(BaseModel):
    ai_enabled: bool
    status: str  # admin | trial | activa | vencida | cancelada | pendiente
    reason: str
    trial_ends_at: Optional[datetime] = None
    trial_active: bool


class TunnelOut(BaseModel):
    """Para el AGENTE local -- incluye el connector_token, necesario para que
    levante `cloudflared` por detrás. Nunca se manda esto al navegador."""

    hostname: str
    connector_token: str


class TunnelPublicOut(BaseModel):
    """Para el panel WEB (botón "Ver en el celular") -- sólo el hostname, nunca
    el connector_token (ese sería equivalente a una llave de acceso al túnel)."""

    hostname: str
    configured: bool  # False = Cloudflare no está configurado en el servidor todavía


# --- Activación local del agente empaquetado (ver routers/local_activation.py) ---
class LocalActivationStatusOut(BaseModel):
    activated: bool
    central_server_configured: bool


class LocalActivateIn(BaseModel):
    email: EmailStr
    password: str


class LocalActivateOut(BaseModel):
    ok: bool
    label: str
