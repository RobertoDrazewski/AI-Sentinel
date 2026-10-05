# -*- mode: python ; coding: utf-8 -*-
import glob
import os

from PyInstaller.utils.hooks import collect_all

datas = [('app/models_data', 'app/models_data'), ('static_frontend', 'static_frontend')]
binaries = []
hiddenimports = ['app.routers.admin', 'app.routers.agent', 'app.routers.alerts', 'app.routers.auth', 'app.routers.cameras', 'app.routers.faces', 'app.routers.local_activation', 'app.routers.stream', 'app.routers.subscription', 'app.routers.telegram', 'app.routers.zones', 'app.phone_home', 'app.device_id', 'app.integrations.cloudflare_client']
tmp_ret = collect_all('ultralytics')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('cv2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# --- Fix RTSP/FFmpeg en Mac: cv2.abi3.so busca sus .dylib de FFmpeg (libavformat,
# libavcodec, etc) en "@loader_path/.dylibs/..." -- o sea una carpeta ".dylibs" al
# lado mismo de cv2.abi3.so dentro del paquete (confirmado con
# `otool -L cv2.abi3.so | grep avformat` -> "@loader_path/.dylibs/libavformat...").
# collect_all('cv2') de arriba encuentra esos .dylib, pero PyInstaller no los termina
# dejando en esa ruta exacta -- así que en tiempo de ejecución el dlopen de FFmpeg
# falla en silencio (sin excepción de Python) y CUALQUIER cv2.VideoCapture(...,
# cv2.CAP_FFMPEG) da isOpened()==False, aunque el mismo código ande perfecto corriendo
# directo desde el venv (sin empaquetar). Sin este bloque, ninguna cámara RTSP puede
# conectar en el agente ya compilado, sea cual sea la marca o la URL.
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
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
