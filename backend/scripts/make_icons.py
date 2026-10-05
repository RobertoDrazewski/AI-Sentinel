"""Genera los íconos para empaquetar el agente de escritorio
(ai-sentinel-agent.spec los usa):

- icon.ico  (Windows, se incrusta en el .exe) -- se genera en cualquier SO, con Pillow.
- icon.icns (macOS, para armar el .app con BUNDLE) -- sólo se genera corriendo en
  Mac, con `iconutil` (viene instalado de fábrica en macOS, no hace falta nada más).

Usa la MISMA imagen que el ícono de "agregar a pantalla de inicio" del panel web
en el celular (frontend/public/icons/icon-512.png), así el programa de escritorio
y el acceso directo del celular se ven iguales -- pedido explícito de Roberto.
"""
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PNG = REPO_ROOT / "frontend" / "public" / "icons" / "icon-512.png"
OUT_DIR = Path(__file__).resolve().parents[1] / "build_icons"


def make_ico(source: Image.Image) -> None:
    out = OUT_DIR / "icon.ico"
    sizes = [16, 32, 48, 64, 128, 256]
    source.save(out, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"icon.ico generado en {out}")


def make_icns(source: Image.Image) -> None:
    if sys.platform != "darwin":
        # iconutil es una herramienta de macOS -- en los runners de Windows/Linux
        # ni hace falta (ahí sólo se usa icon.ico) ni existe el comando.
        print("icon.icns: se salta (sólo se genera corriendo en macOS)")
        return
    iconset = OUT_DIR / "icon.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    # Nombres y tamaños exactos que pide iconutil (normal + @2x para pantallas retina).
    # La fuente es de 512x512 -- el 512x512@2x (1024px) sale agrandado, no 1:1, pero
    # para un ícono de app es indistinguible a simple vista.
    specs = [
        ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024),
    ]
    for name, size in specs:
        resized = source.resize((size, size), Image.LANCZOS)
        resized.save(iconset / name)
    out = OUT_DIR / "icon.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True)
    print(f"icon.icns generado en {out}")


def main() -> None:
    if not SOURCE_PNG.exists():
        raise SystemExit(f"No se encontró el ícono fuente: {SOURCE_PNG}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE_PNG).convert("RGBA")
    make_ico(source)
    make_icns(source)


if __name__ == "__main__":
    main()
