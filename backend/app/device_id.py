"""Huella (fingerprint) de la máquina física donde corre el agente empaquetado.

Se usa para dos cosas, ambas del lado del SERVIDOR CENTRAL:
1. Anti-abuso de trial: si una cuenta nueva se empareja desde una máquina que ya
   usó el trial gratis con OTRA cuenta antes, no le damos otros 30 días gratis
   (ver models.TrialDevice y routers/agent.py pair_agent()).
2. Nada más -- no se usa para "identificar" a la persona, no se manda a ningún
   lado salvo como un hash dentro del pedido de emparejamiento (POST /api/agent/pair).

Nunca se guarda ni se manda el identificador real de hardware -- sólo un hash
(ver hash_fingerprint). No hace falta que sea a prueba de balas: alcanza con
cubrir el caso normal de "dejo vencer el trial, me registro con otro mail para
tener 30 días gratis de nuevo", no un atacante decidido a evadirlo.
"""
from __future__ import annotations

import hashlib
import platform
import re
import subprocess
import uuid


def _read_macos_platform_uuid() -> str | None:
    try:
        out = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
        return match.group(1) if match else None
    except Exception:
        return None


def _read_windows_machine_guid() -> str | None:
    try:
        import winreg  # type: ignore[import-not-found]

        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return str(value)
    except Exception:
        return None


def _read_linux_machine_id() -> str | None:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                value = f.read().strip()
                if value:
                    return value
        except Exception:
            continue
    return None


def get_machine_fingerprint() -> str:
    """Un identificador crudo, estable entre reinicios, de ESTA máquina física.
    No hashear acá -- usar hash_fingerprint() antes de mandarlo a cualquier lado."""
    system = platform.system()
    raw: str | None = None
    if system == "Darwin":
        raw = _read_macos_platform_uuid()
    elif system == "Windows":
        raw = _read_windows_machine_guid()
    elif system == "Linux":
        raw = _read_linux_machine_id()

    if not raw:
        # Último recurso: identificador derivado de la MAC de red. Menos estable
        # (cambia si cambia el adaptador de red principal) pero mejor que nada.
        raw = str(uuid.getnode())

    return f"{system}:{raw}"


def hash_fingerprint(raw: str) -> str:
    """Hash de un solo sentido -- esto es lo único que viaja al servidor central
    y lo único que se guarda en TrialDevice. No se puede reconstruir el
    identificador de hardware original a partir de este hash."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_machine_fingerprint_hash() -> str:
    return hash_fingerprint(get_machine_fingerprint())
