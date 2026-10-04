"""Configuración central de la app. Lee todo desde variables de entorno / .env."""
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_frozen() -> bool:
    """True sólo dentro del ejecutable empaquetado (PyInstaller) que se instala el
    cliente. En desarrollo normal (run.sh) esto siempre da False y nada cambia."""
    return getattr(sys, "frozen", False)


def _user_data_dir() -> Path:
    """Carpeta con permiso de escritura fuera del propio instalador, para guardar lo
    que tiene que sobrevivir a un reinicio o una actualización: la base de datos,
    las fotos de rostros conocidos, los snapshots de alertas. La carpeta donde vive
    el .exe/.app instalado puede ser de sólo lectura o borrarse en una actualización,
    así que nunca guardamos nada ahí."""
    if sys.platform == "win32":
        import os

        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    data_dir = base / "AI Sentinel"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _default(path_name: str, dev_default: str) -> str:
    """En desarrollo (run.sh) devuelve la ruta relativa de siempre, sin cambiar nada
    de lo que ya funciona. Empaquetado (el agente que corre en la PC del cliente)
    devuelve una ruta dentro de la carpeta de datos del usuario."""
    if _is_frozen():
        return str(_user_data_dir() / path_name)
    return dev_default


def _default_database_url() -> str:
    """SQLAlchemy/sqlite necesita distinta cantidad de barras según el formato de la
    ruta absoluta: en Windows ("C:/...") van 3 barras antes de la letra de unidad;
    en Mac/Linux ("/Users/...", ya con su propia barra inicial) van 4 en total."""
    if not _is_frozen():
        return "sqlite:///./centinela.db"
    db_path = (_user_data_dir() / "centinela.db").as_posix()
    slashes = "///" if sys.platform == "win32" else "////"
    return f"sqlite:{slashes}{db_path.lstrip('/')}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SECRET_KEY: str = "dev-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 días
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = _default_database_url()

    MP_ACCESS_TOKEN: str = ""
    MP_PLAN_PRICE_ARS: float = 30000
    MP_WEBHOOK_URL: str = "http://localhost:8000/api/subscription/webhook"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    MODELS_DIR: str = _default("models_data", "app/models_data")
    FACES_DIR: str = _default("known_faces", "app/known_faces")
    SNAPSHOTS_DIR: str = _default("snapshots", "app/snapshots")

    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # Token de emparejamiento del agente local (ver app/routers/agent.py). Se guarda
    # acá, en la carpeta de datos del usuario, la primera vez que el agente empaquetado
    # se loguea con la cuenta -- de ahí en más lo reusa sin pedir contraseña de nuevo.
    AGENT_TOKEN_FILE: str = _default("agent_token.txt", ".agent_token_dev.txt")

    # URL del SERVIDOR CENTRAL (el portal público, ej en Railway) -- SOLO la usa el
    # agente empaquetado (agent_main.py) para activarse y validar la licencia/túnel.
    # Vacío = todavía no se desplegó el servidor central (el agente funciona en modo
    # local nomás, sin licencia remota, como hasta ahora). Ver app/routers/local_activation.py.
    CENTRAL_SERVER_URL: str = ""

    # Credenciales de la API de Cloudflare, para que el SERVIDOR CENTRAL cree un túnel
    # (Cloudflare Tunnel) propio y estable por cada cliente -- ver
    # app/integrations/cloudflare_client.py. Vacío = todavía no se configuró (la función
    # de "ver desde el celular" queda deshabilitada hasta que se complete esto).
    # Alcance recomendado del token: Account > Cloudflare Tunnel > Edit, Zone > DNS > Edit,
    # restringido a la zona de CLOUDFLARE_TUNNEL_DOMAIN solamente.
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_ZONE_ID: str = ""
    # Dominio bajo el cual se crea el subdominio de cada cliente, ej:
    # cliente{user.id}.ai-sentinel.puma-code.com
    CLOUDFLARE_TUNNEL_DOMAIN: str = "ai-sentinel.puma-code.com"


settings = Settings()
