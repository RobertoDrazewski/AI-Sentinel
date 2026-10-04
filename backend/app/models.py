import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite (a diferencia de Postgres) no guarda la zona horaria: un datetime
    "aware" (con zona) que se guarda vuelve "naive" (sin zona) al leerlo de
    nuevo de la base. Como en toda la app generamos las fechas en UTC (ver
    utcnow()), si vuelve sin zona asumimos que es UTC. Sin pasar por esto antes
    de comparar, `datetime.now(timezone.utc) < user.trial_ends_at` tira
    TypeError apenas el usuario viene de una consulta a la base (no de un
    objeto recién creado en memoria) -- por eso no se nota en pruebas rápidas
    pero rompe en el uso real."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def default_trial_end() -> datetime:
    return utcnow() + timedelta(days=30)


def generate_agent_token() -> str:
    # Token largo y opaco para que el agente local lo guarde en disco y lo mande
    # como Bearer en cada pedido -- no es el JWT de la web (ese expira rápido),
    # es de larga duración, pensado para quedar guardado en la PC del cliente.
    return "agt_" + secrets.token_urlsafe(40)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    business_name: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    plan_status: str = Field(default="trial")  # trial | active | past_due | cancelled
    # El primer usuario que se registra en una instalación queda como "admin"
    # automáticamente (ver auth.py y database.py) -- es el dueño de esa instalación
    # y puede ver la pestaña "Admin" con el control de todas las cuentas/suscripciones.
    role: str = Field(default="cliente")  # cliente | admin
    # Prueba gratis de 30 días desde que se registra. Mientras esté vigente, el
    # agente local funciona con reconocimiento/detección inteligente habilitado
    # aunque todavía no haya pagado nada. Ver app/licensing.py.
    trial_ends_at: datetime = Field(default_factory=default_trial_end)


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
    kind: str = Field(default="custom")  # reja | calle | custom | timbre
    # Polígono en coordenadas relativas 0-1 (x,y) para que sea independiente de la resolución.
    # Se guarda como JSON string: "[[x1,y1],[x2,y2],...]"
    polygon_json: str
    loiter_seconds: int = Field(default=5)
    detect_vehicles: bool = Field(default=False)
    detect_people: bool = Field(default=True)
    # Activa el detector de movimiento por flujo óptico sobre la zona. Pensado
    # originalmente para "manipulación de reja", pero se reutiliza tal cual para
    # zonas "timbre" (una mano/brazo que cruza esa zona chica = tocaron el timbre).
    # Qué mensaje/alerta dispara depende de zone.kind, no de este flag.
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


class AgentToken(SQLModel, table=True):
    """Llave de acceso de larga duración para el agente local (el programa que el
    cliente instala en su PC/casa). Se genera UNA vez, cuando el agente se loguea
    por primera vez con el email/contraseña de la cuenta (POST /api/agent/pair), y
    de ahí en más el agente la guarda en disco y la usa en vez de la contraseña.
    Así nunca queda la contraseña guardada en la PC del cliente, y si hay que
    invalidar un dispositivo (se vendió la PC, se robó, etc.) alcanza con borrar
    esta fila sin tocar la cuenta."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token: str = Field(default_factory=generate_agent_token, unique=True, index=True)
    label: str = Field(default="Agente")  # ej: "Mac de Roberto", nombre de la máquina
    created_at: datetime = Field(default_factory=utcnow)
    last_seen_at: Optional[datetime] = None
    # IP pública desde la que consultó por última vez (ver auth.py). No identifica
    # ubicación exacta, pero alcanza para que en el panel Admin se note algo raro
    # -- ej: el mismo token usado desde dos IPs muy distintas el mismo día -- y
    # decidir si conviene revocar el dispositivo.
    last_seen_ip: Optional[str] = None


# Cuántos agentes (PCs) como máximo puede tener emparejados AL MISMO TIEMPO una
# sola cuenta. Pensado para permitir el uso normal (PC de escritorio + notebook,
# o reinstalar en una PC nueva) sin abrir la puerta a que una sola suscripción
# se comparta libremente entre varias personas/casas. Ver routers/agent.py.
MAX_AGENT_DEVICES_PER_USER = 2


class TrialDevice(SQLModel, table=True):
    """Para notar si una PC física ya usó la prueba gratis de 30 días con OTRA
    cuenta antes de ahora -- si alguien deja vencer el trial sin pagar y se
    registra de nuevo con un mail distinto en la misma máquina para "renovar"
    los 30 días gratis, a esa cuenta nueva no se los damos (ver pair_agent en
    routers/agent.py: si el fingerprint ya está acá con OTRO user_id, el
    trial de la cuenta nueva queda vencido desde el momento en que se activa).
    No bloqueamos el emparejamiento en sí -- la app le sigue andando sin IA
    hasta que pague, igual que a cualquier cuenta con el trial vencido.

    fingerprint_hash es un hash (nunca el ID real de hardware) de un
    identificador estable de la máquina -- ver app/device_id.py en el lado
    del agente. No es a prueba de balas (alguien técnico podría forzarlo a
    cambiar), pero cubre el caso normal de "me registro de nuevo para otros
    30 días gratis" sin pedirle nada raro al usuario ni tocar su privacidad
    (no se guarda ningún dato personal, sólo el hash)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    fingerprint_hash: str = Field(unique=True, index=True)
    first_user_id: int = Field(foreign_key="user.id")
    first_seen_at: datetime = Field(default_factory=utcnow)


class ClientTunnel(SQLModel, table=True):
    """Túnel de Cloudflare propio y ESTABLE de este cliente (el subdominio no
    cambia nunca, a diferencia de un "Quick Tunnel") -- ver
    app/integrations/cloudflare_client.py. Se crea una sola vez, la primera
    vez que el agente local lo pide (GET /api/agent/tunnel); de ahí en más
    siempre se reusa el mismo. cf_connector_token es lo que el agente necesita
    para levantar `cloudflared` por detrás -- es sensible (equivale a una
    llave de acceso a ese túnel), así que sólo se lo mandamos al propio
    agente autenticado, nunca a la respuesta que lee el navegador."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    subdomain: str = Field(unique=True, index=True)
    hostname: str
    cf_tunnel_id: str
    cf_connector_token: str
    created_at: datetime = Field(default_factory=utcnow)


class Payment(SQLModel, table=True):
    """Un registro por cada pago mensual aprobado (vía webhook de Mercado Pago, o vía
    /simulate-payment en desarrollo). A diferencia de Subscription (que sólo guarda el
    estado ACTUAL), esto es el historial completo -- lo que el cliente ve en "Mi cuenta"
    como "pagos de este mes" y lo que usamos para calcular la próxima fecha de vencimiento
    (último pago + 1 mes)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    mp_payment_id: Optional[str] = Field(default=None, index=True)
    amount_ars: float
    status: str = Field(default="aprobado")  # aprobado | rechazado
    paid_at: datetime = Field(default_factory=utcnow)
