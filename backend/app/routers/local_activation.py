"""Endpoints LOCALES SOLAMENTE -- los usa la pantalla de "activación" del propio
agente empaquetado (corriendo en localhost:8000 en la PC del cliente), nunca el
panel público. No requieren login en la base local (que recién se crea en este
mismo paso) -- hablan directo con el SERVIDOR CENTRAL usando el email/contraseña
que el cliente ya tiene de cuando se registró en el portal público.

Flujo:
1. El agente arranca. Si no existe todavía settings.AGENT_TOKEN_FILE, muestra la
   pantalla de activación en vez del dashboard normal.
2. Esa pantalla llama GET /activation-status para saber si hace falta activar.
3. El cliente pone su email/contraseña (los mismos de la cuenta) y el frontend
   llama POST /activate.
4. Este endpoint hace de intermediario: se loguea en el SERVIDOR CENTRAL
   (POST {CENTRAL_SERVER_URL}/api/auth/login) para obtener un JWT corto, y con
   ese JWT llama a {CENTRAL_SERVER_URL}/api/agent/pair (mandando device_fingerprint
   y un label con el nombre de esta máquina) para obtener el AgentToken de larga
   duración, que guarda en AGENT_TOKEN_FILE. De ahí en más, agent_main.py usa ese
   token para todo (licencia, túnel) sin volver a pedir contraseña."""
from __future__ import annotations

import socket

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import hash_password
from app.config import settings
from app.database import get_session
from app.device_id import get_machine_fingerprint_hash
from app.models import User
from app.schemas import LocalActivateIn, LocalActivateOut, LocalActivationStatusOut

router = APIRouter(prefix="/api/local", tags=["local"])


def _is_activated() -> bool:
    try:
        with open(settings.AGENT_TOKEN_FILE, "r", encoding="utf-8") as f:
            return bool(f.read().strip())
    except FileNotFoundError:
        return False


@router.get("/activation-status", response_model=LocalActivationStatusOut)
def activation_status():
    return LocalActivationStatusOut(
        activated=_is_activated(),
        central_server_configured=bool(settings.CENTRAL_SERVER_URL),
    )


@router.post("/activate", response_model=LocalActivateOut)
def activate(data: LocalActivateIn, session: Session = Depends(get_session)):
    if not settings.CENTRAL_SERVER_URL:
        raise HTTPException(
            status_code=503,
            detail="Este agente todavía no tiene configurado el servidor central (CENTRAL_SERVER_URL).",
        )
    base = settings.CENTRAL_SERVER_URL.rstrip("/")

    try:
        login_resp = requests.post(
            f"{base}/api/auth/login",
            json={"email": data.email, "password": data.password},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar al servidor: {exc}")

    if login_resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    jwt = login_resp.json()["access_token"]
    label = socket.gethostname() or "Agente"

    try:
        pair_resp = requests.post(
            f"{base}/api/agent/pair",
            headers={"Authorization": f"Bearer {jwt}"},
            json={"label": label, "device_fingerprint": get_machine_fingerprint_hash()},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar al servidor: {exc}")

    if pair_resp.status_code == 409:
        # Tope de dispositivos alcanzado -- mensaje tal cual lo manda el servidor.
        raise HTTPException(status_code=409, detail=pair_resp.json().get("detail"))
    if pair_resp.status_code != 200:
        raise HTTPException(status_code=502, detail="No se pudo activar el agente con el servidor.")

    agent_token = pair_resp.json()["token"]
    with open(settings.AGENT_TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(agent_token)

    # Emparejar el agente con el servidor central NO crea ninguna cuenta en la base
    # LOCAL de esta PC (esa base arranca vacía en cada instalación nueva) -- y el
    # /login de acá en más (pantalla normal del panel) valida contra esa base local,
    # no contra el servidor central. Sin este paso, ese login nunca iba a funcionar:
    # nadie llenaba la base local. Creamos (o, si ya existía, actualizamos la
    # contraseña de) un usuario local con el mismo mail/contraseña que el cliente
    # ya validó recién contra el servidor central, para que pueda loguearse acá.
    local_user = session.exec(select(User).where(User.email == data.email)).first()
    if local_user is None:
        is_first_user = session.exec(select(User)).first() is None
        local_user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            role="admin" if is_first_user else "cliente",
        )
        session.add(local_user)
    else:
        local_user.password_hash = hash_password(data.password)
    session.commit()

    return LocalActivateOut(ok=True, label=label)
