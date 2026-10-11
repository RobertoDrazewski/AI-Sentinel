"""Túnel estable por cliente, vía la API de Cloudflare Tunnel.

Cada cliente que paga (o está en el trial) puede pedir "ver desde el celular" --
eso necesita que su agente local, corriendo en una PC detrás de un router de
casa (sin IP pública ni puerto abierto), sea alcanzable desde afuera. En vez de
pedirle al cliente que abra puertos en su router (inseguro y la mayoría no sabe
hacerlo), el SERVIDOR CENTRAL crea un túnel de Cloudflare por cuenta, con un
subdominio fijo que no cambia nunca (ej: ai-sentinel-cliente42.puma-code.com --
UN solo nivel bajo el apex, no dos, para que quede cubierto por el certificado
SSL gratuito de Cloudflare: ver el comentario de CLOUDFLARE_TUNNEL_DOMAIN en
config.py), y le manda al agente el "connector token" para que levante `cloudflared` por
detrás. Cloudflare hace de intermediario: la PC de casa se conecta HACIA
afuera (eso sí lo deja pasar cualquier router sin configurar nada) y Cloudflare
enruta las visitas al subdominio hacia esa conexión.

Requiere tres variables de entorno en el servidor central (nunca en el agente
del cliente): CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_ZONE_ID.
Ver app/config.py para el alcance recomendado del token.
"""
from __future__ import annotations

from typing import Optional

import requests

from app.config import settings

API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(
        settings.CLOUDFLARE_API_TOKEN
        and settings.CLOUDFLARE_ACCOUNT_ID
        and settings.CLOUDFLARE_ZONE_ID
    )


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }


def _check(resp: requests.Response, action: str) -> dict:
    data = resp.json()
    if not resp.ok or not data.get("success"):
        raise CloudflareError(f"Cloudflare falló al {action}: {data.get('errors')}")
    return data


def _find_dns_record_id(hostname: str) -> Optional[str]:
    """Busca si ya existe un registro DNS con este nombre exacto en la zona (sin
    importar el tipo). Cloudflare no permite un CNAME nuevo si ya hay CUALQUIER
    otro registro con el mismo nombre -- hace falta encontrarlo primero para
    poder borrarlo antes de crear el nuevo."""
    zone_id = settings.CLOUDFLARE_ZONE_ID
    resp = requests.get(
        f"{API_BASE}/zones/{zone_id}/dns_records",
        headers=_headers(),
        params={"name": hostname},
        timeout=15,
    )
    data = _check(resp, "buscar el registro DNS existente")
    results = data.get("result") or []
    return results[0]["id"] if results else None


def _delete_dns_record_if_exists(hostname: str) -> None:
    record_id = _find_dns_record_id(hostname)
    if record_id is None:
        return
    requests.delete(
        f"{API_BASE}/zones/{settings.CLOUDFLARE_ZONE_ID}/dns_records/{record_id}",
        headers=_headers(),
        timeout=15,
    )


def create_tunnel_for_subdomain(subdomain: str) -> dict:
    """Crea el túnel + la regla de ingreso + el registro DNS para `subdomain`
    (ej: "cliente42"). Devuelve {tunnel_id, connector_token, hostname}.

    Se llama UNA sola vez por cliente -- de ahí en más el resultado se guarda
    en la tabla ClientTunnel y se reusa siempre (ver routers/agent.py). Como el
    hostname es siempre el mismo para la misma cuenta, si quedó un registro DNS
    huérfano de un túnel anterior (ver delete_tunnel) hay que borrarlo PRIMERO --
    si no, el paso 4 de acá abajo falla porque Cloudflare no deja crear un CNAME
    con un nombre que ya está en uso, y la cuenta queda sin "ver desde el
    celular" para siempre hasta que alguien lo note y lo borre a mano."""
    if not is_configured():
        raise CloudflareError("Cloudflare no está configurado en el servidor (faltan variables de entorno).")

    hostname = f"{subdomain}.{settings.CLOUDFLARE_TUNNEL_DOMAIN}"
    account_id = settings.CLOUDFLARE_ACCOUNT_ID
    zone_id = settings.CLOUDFLARE_ZONE_ID

    _delete_dns_record_if_exists(hostname)

    # 1) Crear el túnel (config administrado por Cloudflare, no por un archivo local).
    create_resp = requests.post(
        f"{API_BASE}/accounts/{account_id}/cfd_tunnel",
        headers=_headers(),
        json={"name": f"ai-sentinel-{subdomain}", "config_src": "cloudflare"},
        timeout=15,
    )
    tunnel = _check(create_resp, "crear el túnel")["result"]
    tunnel_id = tunnel["id"]

    # 2) Pedir el token de conector -- esto es lo que usa `cloudflared tunnel run
    # --token <token>` en la PC del cliente.
    token_resp = requests.get(
        f"{API_BASE}/accounts/{account_id}/cfd_tunnel/{tunnel_id}/token",
        headers=_headers(),
        timeout=15,
    )
    connector_token = _check(token_resp, "obtener el token del túnel")["result"]

    # 3) Configurar la regla de ingreso: todo tráfico a `hostname` va al puerto
    # 8000 local (donde corre el agente empaquetado).
    config_resp = requests.put(
        f"{API_BASE}/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
        headers=_headers(),
        json={
            "config": {
                "ingress": [
                    {"hostname": hostname, "service": "http://localhost:8000"},
                    {"service": "http_status:404"},
                ]
            }
        },
        timeout=15,
    )
    _check(config_resp, "configurar el túnel")

    # 4) Crear el registro DNS (CNAME hacia <tunnel_id>.cfargotunnel.com, proxiado).
    dns_resp = requests.post(
        f"{API_BASE}/zones/{zone_id}/dns_records",
        headers=_headers(),
        json={
            "type": "CNAME",
            "name": hostname,
            "content": f"{tunnel_id}.cfargotunnel.com",
            "proxied": True,
        },
        timeout=15,
    )
    _check(dns_resp, "crear el registro DNS")

    return {"tunnel_id": tunnel_id, "connector_token": connector_token, "hostname": hostname}


def delete_tunnel(tunnel_id: str, hostname: Optional[str] = None) -> None:
    """Borra el túnel en Cloudflare. Se usa si alguna vez hay que limpiar uno roto
    (ej: la cuenta se dio de baja, o el botón "Reiniciar túnel" en Suscripción).

    Si se pasa `hostname`, también borra su registro DNS. ANTES esto se dejaba
    huérfano a propósito ("no hace daño"), pero sí hace daño: como el hostname
    de cada cuenta es siempre el mismo (ai-sentinel-cliente{id}...), ese
    registro viejo le gana el nombre al que create_tunnel_for_subdomain intenta
    crear la próxima vez, y la cuenta queda con "ver desde el celular" roto
    para siempre (sin ningún error visible para el cliente, sólo el cartel de
    "todavía no está disponible"). create_tunnel_for_subdomain ya se protege
    de este caso por las dudas, pero borrarlo acá también evita dejar basura
    dando vueltas en el panel de Cloudflare."""
    if not is_configured():
        return
    requests.delete(
        f"{API_BASE}/accounts/{settings.CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel/{tunnel_id}",
        headers=_headers(),
        timeout=15,
    )
    if hostname:
        try:
            _delete_dns_record_if_exists(hostname)
        except CloudflareError:
            pass  # no es crítico -- create_tunnel_for_subdomain se cubre solo igual
