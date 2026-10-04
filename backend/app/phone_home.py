""""Phone home": sólo corre DENTRO del agente empaquetado (sys.frozen), nunca en
el servidor central. Es el puente entre el agente local (que vive en la PC de
cada cliente, con su propia base SQLite vacía/aislada) y el SERVIDOR CENTRAL
(donde vive la cuenta real: trial, suscripción, pagos).

Por qué hace falta esto en vez de usar directamente `app/licensing.py` y la
tabla ClientTunnel de siempre: ESTE proceso (el agente) tiene su propia base de
datos local, separada de la del servidor central -- ahí no hay una fila de
Subscription real ni de ClientTunnel (esas viven en el servidor). Así que,
estando empaquetado, en vez de calcular la licencia/túnel con la base local,
este módulo los consulta periódicamente al servidor central (usando el
AgentToken que se obtuvo al activarse, ver app/routers/local_activation.py) y
los deja en una cachecita en memoria. routers/agent.py lee esa caché (sólo
cuando _is_frozen()) en vez de mirar la base local.

Si el agente nunca se activó (no existe AGENT_TOKEN_FILE todavía) o
CENTRAL_SERVER_URL no está configurado, este módulo simplemente no hace nada
-- el agente sigue funcionando como siempre (sin esta capa).
"""
from __future__ import annotations

import logging
import platform
import stat
import subprocess
import tarfile
import threading
import time
from pathlib import Path
from typing import Optional

import requests

from app.config import settings

log = logging.getLogger("phone_home")

# Cada cuánto se vuelve a consultar al servidor central mientras el agente está
# corriendo. No hace falta más seguido que esto -- ver routers/agent.py license_status.
_POLL_INTERVAL_SECONDS = 60 * 60  # 1 hora
_RETRY_INTERVAL_SECONDS = 60  # si falla (sin internet, servidor caído), reintenta más seguido

_lock = threading.Lock()
_cached_license: Optional[dict] = None
_cached_tunnel_hostname: Optional[str] = None
_cloudflared_process: Optional[subprocess.Popen] = None
_cloudflared_token_running: Optional[str] = None


def get_cached_license() -> Optional[dict]:
    with _lock:
        return dict(_cached_license) if _cached_license else None


def get_cached_tunnel_hostname() -> Optional[str]:
    with _lock:
        return _cached_tunnel_hostname


def _read_agent_token() -> Optional[str]:
    try:
        with open(settings.AGENT_TOKEN_FILE, "r", encoding="utf-8") as f:
            token = f.read().strip()
            return token or None
    except FileNotFoundError:
        return None


def _central_get(path: str, agent_token: str) -> Optional[dict]:
    base = settings.CENTRAL_SERVER_URL.rstrip("/")
    try:
        resp = requests.get(
            f"{base}{path}",
            headers={"Authorization": f"Bearer {agent_token}"},
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning("Servidor central respondió %s en %s", resp.status_code, path)
            return None
        return resp.json()
    except requests.RequestException as exc:
        log.warning("No se pudo contactar al servidor central (%s): %s", path, exc)
        return None


# --- cloudflared: binario + proceso ---

def _cloudflared_bin_dir() -> Path:
    from app.config import _user_data_dir

    d = _user_data_dir() / "bin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cloudflared_bin_path() -> Path:
    name = "cloudflared.exe" if platform.system() == "Windows" else "cloudflared"
    return _cloudflared_bin_dir() / name


def _download_cloudflared_asset_name() -> Optional[str]:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "cloudflared-windows-amd64.exe"
    if system == "Darwin":
        if machine in ("arm64", "aarch64"):
            return "cloudflared-darwin-arm64.tgz"
        return "cloudflared-darwin-amd64.tgz"
    if system == "Linux":
        if "arm" in machine or "aarch64" in machine:
            return "cloudflared-linux-arm64"
        return "cloudflared-linux-amd64"
    return None


def ensure_cloudflared_binary() -> Optional[Path]:
    """Descarga `cloudflared` UNA sola vez por máquina (queda guardado en la
    carpeta de datos del usuario, al lado de la base local) -- evita tener que
    agregarlo al empaquetado de PyInstaller / a la compilación en CI."""
    dest = _cloudflared_bin_path()
    if dest.exists():
        return dest

    asset_name = _download_cloudflared_asset_name()
    if not asset_name:
        log.warning("Sistema operativo no soportado para el túnel (%s)", platform.system())
        return None

    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{asset_name}"
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("No se pudo descargar cloudflared: %s", exc)
        return None

    download_path = _cloudflared_bin_dir() / asset_name
    download_path.write_bytes(resp.content)

    if asset_name.endswith(".tgz"):
        with tarfile.open(download_path, "r:gz") as tar:
            tar.extractall(_cloudflared_bin_dir())
        download_path.unlink(missing_ok=True)
        extracted = _cloudflared_bin_dir() / "cloudflared"
        if extracted.exists() and extracted != dest:
            extracted.rename(dest)
    else:
        download_path.rename(dest)

    if platform.system() != "Windows":
        dest.chmod(dest.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    return dest


def _ensure_tunnel_running(connector_token: str) -> None:
    global _cloudflared_process, _cloudflared_token_running

    if _cloudflared_process is not None and _cloudflared_token_running == connector_token:
        if _cloudflared_process.poll() is None:
            return  # ya está corriendo con el mismo token, nada que hacer

    binary = ensure_cloudflared_binary()
    if binary is None:
        return

    if _cloudflared_process is not None and _cloudflared_process.poll() is None:
        _cloudflared_process.terminate()

    try:
        _cloudflared_process = subprocess.Popen(
            [str(binary), "tunnel", "run", "--token", connector_token],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _cloudflared_token_running = connector_token
        log.info("Túnel de Cloudflare iniciado")
    except OSError as exc:
        log.warning("No se pudo iniciar cloudflared: %s", exc)


def _sync_once() -> bool:
    """Un ciclo de sincronización. Devuelve True si pudo hablar con el servidor
    (para decidir cuánto esperar antes del próximo intento)."""
    global _cached_license, _cached_tunnel_hostname

    if not settings.CENTRAL_SERVER_URL:
        return False
    agent_token = _read_agent_token()
    if not agent_token:
        return False  # todavía no se activó -- ver app/routers/local_activation.py

    ok = False

    license_data = _central_get("/api/agent/license", agent_token)
    if license_data is not None:
        with _lock:
            _cached_license = license_data
        ok = True

    tunnel_data = _central_get("/api/agent/tunnel", agent_token)
    if tunnel_data is not None:
        with _lock:
            _cached_tunnel_hostname = tunnel_data.get("hostname")
        connector_token = tunnel_data.get("connector_token")
        if connector_token:
            _ensure_tunnel_running(connector_token)
        ok = True

    return ok


def _loop() -> None:
    while True:
        try:
            ok = _sync_once()
        except Exception:  # nunca puede tirar abajo el agente por esto
            log.exception("Error inesperado sincronizando con el servidor central")
            ok = False
        time.sleep(_POLL_INTERVAL_SECONDS if ok else _RETRY_INTERVAL_SECONDS)


def start_background_sync() -> None:
    """Se llama una vez al arrancar el agente empaquetado (ver agent_main.py). Si
    no hay servidor central configurado o el agente no está activado todavía,
    el hilo corre pero no hace nada hasta que se active (ver _sync_once)."""
    if not settings.CENTRAL_SERVER_URL:
        return
    thread = threading.Thread(target=_loop, name="phone-home-sync", daemon=True)
    thread.start()
