from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import get_current_user
from app.config import _is_frozen
from app.database import get_session
from app.integrations import cloudflare_client
from app.licensing import compute_license_status
from app.models import (
    MAX_AGENT_DEVICES_PER_USER,
    AgentToken,
    ClientTunnel,
    Subscription,
    TrialDevice,
    User,
    ensure_aware,
    utcnow,
)
from app.schemas import (
    AgentDeviceOut,
    AgentPairIn,
    AgentPairOut,
    LicenseStatusOut,
    TunnelOut,
    TunnelPublicOut,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/pair", response_model=AgentPairOut)
def pair_agent(
    data: AgentPairIn,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """El agente local llama acá UNA sola vez, recién instalado, usando el JWT que
    obtuvo al loguearse con el email/contraseña de la cuenta (igual que el panel
    web). A cambio le damos un token de larga duración que guarda en disco y usa
    de ahí en más -- así la contraseña nunca queda guardada en la PC del cliente.

    Tope de MAX_AGENT_DEVICES_PER_USER dispositivos emparejados a la vez por
    cuenta (pensado para una PC de escritorio + una notebook, o reinstalar sin
    drama) -- evita que una sola suscripción se comparta libremente entre varias
    personas/casas. Si ya está en el tope, hay que borrar un dispositivo viejo
    desde "Mi cuenta" antes de poder emparejar uno nuevo.

    Anti-abuso de trial: si manda device_fingerprint y esa máquina física ya
    emparejó antes con OTRA cuenta, el trial de ESTA cuenta queda vencido ya
    mismo (no se bloquea el emparejamiento -- la app sigue andando sin IA hasta
    que pague, igual que cualquier cuenta con el trial vencido)."""
    existing = session.exec(
        select(AgentToken).where(AgentToken.user_id == current_user.id)
    ).all()
    if len(existing) >= MAX_AGENT_DEVICES_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Esta cuenta ya tiene {MAX_AGENT_DEVICES_PER_USER} dispositivos emparejados "
                "(el máximo permitido por suscripción). Borrá uno desde \"Mi cuenta\" antes de "
                "activar uno nuevo."
            ),
        )

    if data.device_fingerprint:
        known = session.exec(
            select(TrialDevice).where(TrialDevice.fingerprint_hash == data.device_fingerprint)
        ).first()
        if known is None:
            session.add(
                TrialDevice(fingerprint_hash=data.device_fingerprint, first_user_id=current_user.id)
            )
        elif known.first_user_id != current_user.id and ensure_aware(current_user.trial_ends_at) > utcnow():
            # Esta máquina ya usó el trial con otra cuenta -- no le damos otros
            # 30 días gratis a esta cuenta nueva.
            current_user.trial_ends_at = utcnow()
            session.add(current_user)

    token_row = AgentToken(user_id=current_user.id, label=data.label or "Agente")
    session.add(token_row)
    session.commit()
    session.refresh(token_row)
    return AgentPairOut(token=token_row.token, label=token_row.label, device_id=token_row.id)


@router.get("/devices", response_model=list[AgentDeviceOut])
def list_devices(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """Para la pantalla "Mi cuenta": qué agentes (PCs) están emparejados con esta
    cuenta, para poder revocar uno si hace falta (se vendió la PC, etc.)."""
    rows = session.exec(
        select(AgentToken).where(AgentToken.user_id == current_user.id)
    ).all()
    return [
        AgentDeviceOut(
            id=r.id,
            label=r.label,
            created_at=r.created_at,
            last_seen_at=r.last_seen_at,
            last_seen_ip=r.last_seen_ip,
        )
        for r in rows
    ]


@router.delete("/devices/{device_id}")
def revoke_device(
    device_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    row = session.get(AgentToken, device_id)
    if not row or row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="No encontrado")
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.get("/license", response_model=LicenseStatusOut)
def license_status(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """El agente local (y el panel web) consultan esto para saber si la parte
    inteligente (reconocimiento facial, detección de zonas, alertas) tiene que
    estar prendida o apagada en este momento. Pensado para que el agente lo
    chequee al arrancar y después cada 1 hora o así -- no hace falta más
    frecuencia que esa.

    Corriendo DENTRO del agente empaquetado y ya activado (ver
    app/phone_home.py), la base local no tiene una Subscription real -- esa
    vive en el servidor central. Por eso, en ese caso, se devuelve lo último
    que phone_home trajo del servidor central en vez de calcularlo con la
    base local."""
    if _is_frozen():
        from app import phone_home

        cached = phone_home.get_cached_license()
        if cached is not None:
            return LicenseStatusOut(**cached)

    sub = session.exec(
        select(Subscription).where(Subscription.user_id == current_user.id)
    ).first()
    return LicenseStatusOut(**compute_license_status(current_user, sub))


def _get_or_create_tunnel(session: Session, current_user: User) -> ClientTunnel:
    tunnel = session.exec(
        select(ClientTunnel).where(ClientTunnel.user_id == current_user.id)
    ).first()
    if tunnel is not None:
        return tunnel

    # "ai-sentinel-cliente{id}" en vez de "cliente{id}.ai-sentinel" -- tiene
    # que quedar como UN solo nivel bajo el apex de CLOUDFLARE_TUNNEL_DOMAIN
    # para que lo cubra el certificado SSL gratis de Cloudflare (ver el
    # comentario largo en config.py sobre CLOUDFLARE_TUNNEL_DOMAIN).
    subdomain = f"ai-sentinel-cliente{current_user.id}"
    result = cloudflare_client.create_tunnel_for_subdomain(subdomain)
    tunnel = ClientTunnel(
        user_id=current_user.id,
        subdomain=subdomain,
        hostname=result["hostname"],
        cf_tunnel_id=result["tunnel_id"],
        cf_connector_token=result["connector_token"],
    )
    session.add(tunnel)
    session.commit()
    session.refresh(tunnel)
    return tunnel


@router.delete("/tunnel")
def reset_tunnel(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """Borra el túnel guardado de esta cuenta (en Cloudflare y en la base) para
    que se vuelva a crear de cero la próxima vez que se pida (GET /tunnel o
    /tunnel/public). Pensado para los túneles que se crearon ANTES del fix del
    hostname de dos niveles (ver CLOUDFLARE_TUNNEL_DOMAIN en config.py) y
    quedaron con un subdominio que el SSL de Cloudflare nunca va a cubrir --
    sin esto quedarían rotos para siempre, porque _get_or_create_tunnel reusa
    lo que ya esté guardado. También sirve si el túnel se corrompe por
    cualquier otro motivo."""
    tunnel = session.exec(
        select(ClientTunnel).where(ClientTunnel.user_id == current_user.id)
    ).first()
    if tunnel is None:
        return {"ok": True, "deleted": False}
    cloudflare_client.delete_tunnel(tunnel.cf_tunnel_id, tunnel.hostname)
    session.delete(tunnel)
    session.commit()
    return {"ok": True, "deleted": True}


@router.get("/tunnel", response_model=TunnelOut)
def get_tunnel(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """SOLO lo llama el agente empaquetado (nunca el navegador) -- devuelve el
    connector_token que necesita para levantar `cloudflared` y quedar accesible
    desde ai-sentinel-cliente{id}.puma-code.com. Se crea una sola vez por
    cuenta y de ahí en más siempre se reusa el mismo túnel/subdominio (ver
    DELETE /tunnel para forzar que se recree)."""
    if not cloudflare_client.is_configured():
        raise HTTPException(
            status_code=503,
            detail="El servidor todavía no tiene configurado Cloudflare para los túneles.",
        )
    tunnel = _get_or_create_tunnel(session, current_user)
    return TunnelOut(hostname=tunnel.hostname, connector_token=tunnel.cf_connector_token)


@router.get("/tunnel/public", response_model=TunnelPublicOut)
def get_tunnel_public(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
):
    """La llama el panel WEB (botón "Ver en el celular" / código QR) -- a
    diferencia de /tunnel, nunca devuelve el connector_token. Si Cloudflare no
    está configurado todavía en el servidor, el frontend muestra un mensaje en
    vez del QR.

    Corriendo DENTRO del agente empaquetado: el túnel en sí lo crea y lo guarda
    el SERVIDOR CENTRAL (esta misma base local no tiene esa tabla con datos
    reales) -- ver app/phone_home.py, que ya lo consultó por su cuenta y lo
    tiene cacheado.

    Corriendo en el servidor central: si la cuenta todavía no tiene un túnel
    guardado, lo crea ACÁ MISMO en vez de limitarse a avisar que falta -- antes
    el cliente dependía de que su agente local llamara GET /tunnel por su
    cuenta (al prenderse, o una vez por hora), así que podía quedarse mirando
    "todavía no está disponible" sin ningún botón para apurarlo. Con esto,
    simplemente entrar a Suscripción ya alcanza para que aparezca el QR, sin
    esperar a que el agente sincronice solo."""
    if _is_frozen():
        from app import phone_home

        hostname = phone_home.get_cached_tunnel_hostname()
        return TunnelPublicOut(hostname=hostname or "", configured=bool(hostname))

    if not cloudflare_client.is_configured():
        return TunnelPublicOut(hostname="", configured=False)
    try:
        tunnel = _get_or_create_tunnel(session, current_user)
    except cloudflare_client.CloudflareError:
        return TunnelPublicOut(hostname="", configured=False)
    return TunnelPublicOut(hostname=tunnel.hostname, configured=True)
