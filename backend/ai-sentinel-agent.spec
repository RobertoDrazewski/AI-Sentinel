# -*- mode: python ; coding: utf-8 -*-
import glob
import os
import sys

from PyInstaller.utils.hooks import collect_all

# Generados antes de este paso por scripts/make_icons.py (ver build-agent.yml),
# a partir del mismo ícono que usa el panel web para "agregar a pantalla de
# inicio" en el celular -- así el programa de escritorio y el acceso directo
# del celular se ven iguales.
ICO_PATH = "build_icons/icon.ico"
ICNS_PATH = "build_icons/icon.icns"

datas = [('app/models_data', 'app/models_data'), ('static_frontend', 'static_frontend')]
binaries = []
hiddenimports = ['app.routers.admin', 'app.routers.agent', 'app.routers.alerts', 'app.routers.auth', 'app.routers.cameras', 'app.routers.faces', 'app.routers.local_activation', 'app.routers.stream', 'app.routers.subscription', 'app.routers.telegram', 'app.routers.zones', 'app.phone_home', 'app.device_id', 'app.integrations.cloudflare_client']
tmp_ret = collect_all('ultralytics')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('cv2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Red de seguridad por si acaso: aseguramos que los .dylib de FFmpeg que trae cv2
# (libavformat, libavcodec, etc -- cv2.abi3.so los busca en "@loader_path/.dylibs/...",
# confirmado con `otool -L cv2.abi3.so | grep avformat`) terminen en esa ruta exacta
# dentro del paquete. Probado: esto NO era la causa real del problema (si faltaran,
# el agente ni arrancaría -- "import cv2" fallaría entero, y acá arranca bien y sólo
# falla al abrir streams RTSP) pero no hace daño dejarlo.
import cv2 as _cv2_probe  # noqa: E402  (import acá a propósito: el .spec corre como script de build)

_cv2_dylibs_dir = os.path.join(os.path.dirname(_cv2_probe.__file__), '.dylibs')
for _dylib in glob.glob(os.path.join(_cv2_dylibs_dir, '*.dylib')):
    binaries.append((_dylib, 'cv2/.dylibs'))


a = Analysis(
    ['agent_main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ai-sentinel-agent',
    icon=ICO_PATH,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # Causa real (probable) del fallo de RTSP en el agente compilado: UPX comprimiendo
    # los .dylib de FFmpeg en Mac es un problema conocido -- la app arranca bien y
    # "import cv2" funciona (la compresión no rompe la carga de la librería en sí),
    # pero puede romper el mecanismo interno con el que FFmpeg "registra" sus
    # protocolos (rtsp, http, etc) al cargar, dejando avformat_open_input() sin
    # ningún handler para "rtsp://" -- exactamente lo que estamos viendo: todo anda
    # menos abrir streams RTSP, y sin ningún error de Python. Si esto confirma el
    # arreglo, lo ideal sería agregar sólo los .dylib de FFmpeg a upx_exclude en vez
    # de desactivarlo en todo el ejecutable (el único costo de esto es un binario
    # final más pesado, no hay downside funcional).
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# En Mac, sin esto el resultado es un binario Unix suelto -- Finder no lo
# reconoce como aplicación (queda como "Documento"), no tiene ícono propio y al
# abrirlo con doble clic/clic derecho intenta mostrarlo como texto en vez de
# ejecutarlo. BUNDLE lo empaqueta como una app de Mac de verdad ("AI
# Sentinel.app", con su Info.plist y su ícono), para poder abrirla con doble
# clic como cualquier otro programa. En Windows/Linux, BUNDLE no hace nada
# (PyInstaller lo ignora fuera de macOS), así que no hace falta "if" para
# esos SO -- lo dejamos explícito igual, para que quede claro a qué SO aplica.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name='AI Sentinel.app',
        icon=ICNS_PATH,
        bundle_identifier='com.pumacode.aisentinel',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
        },
    )
