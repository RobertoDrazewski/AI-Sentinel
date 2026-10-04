"""Punto de entrada del AGENTE LOCAL empaquetado (lo que arma PyInstaller para el
.exe de Windows y el .app/.pkg de Mac). No se usa en desarrollo -- ahí seguís
usando run.sh / uvicorn app.main:app --reload como siempre, sin tocar nada de
esto. Esto es específicamente lo que corre dentro del instalador que se baja
el cliente.

Lo que hace, en orden:
1. Marca a la app que esto es un "frozen build" (lo hace solo PyInstaller) --
   eso hace que app/config.py guarde todo en la carpeta de datos del usuario
   en vez de rutas relativas al instalador.
2. Copia los modelos de IA desde el bundle (sólo lectura) a esa carpeta, la
   primera vez que corre en esta máquina.
3. Abre el navegador en http://localhost:8000 un segundo y medio después de
   arrancar -- tiempo de sobra para que uvicorn ya esté escuchando.
4. Arranca el servidor, igual que hace run.sh.
5. Si ya está activado (ver app/routers/local_activation.py) y el build tiene
   configurado un servidor central, arranca en segundo plano la sincronización
   de licencia/túnel contra ese servidor (ver app/phone_home.py). Si todavía no
   se activó, o no hay servidor central configurado, esto no hace nada -- el
   agente sigue funcionando exactamente como antes.
"""
import os
import shutil
import sys
import threading
import webbrowser
from pathlib import Path


def _bundled_resource_path(relative: str) -> Path:
    """Carpeta de sólo lectura donde PyInstaller deja los archivos empaquetados con
    --add-data (modelos de IA, frontend compilado). sys._MEIPASS sólo existe
    dentro del ejecutable ya armado."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / relative


def _ensure_models_copied(models_dir: str) -> None:
    """Primera vez que corre en esta máquina: copia los modelos de IA (reconocimiento
    facial YuNet/SFace Y el yolov8n.pt de detección de objetos -- los tres quedan
    juntos en app/models_data al armar el instalador, ver .github/workflows) desde
    el bundle hacia la carpeta de datos del usuario (con permiso de escritura), para
    no tener que descargar nada de internet en lo de cada cliente."""
    dest = Path(models_dir)
    dest.mkdir(parents=True, exist_ok=True)
    src = _bundled_resource_path("app/models_data")
    if not src.is_dir():
        return
    for f in src.iterdir():
        target = dest / f.name
        if not target.exists():
            shutil.copy2(f, target)


def main() -> None:
    # PyInstaller define sys.frozen automáticamente en el ejecutable final -- pero
    # lo reforzamos acá por si alguna vez se corre este archivo suelto para probar.
    sys.frozen = True  # type: ignore[attr-defined]

    from app.config import settings  # import DESPUÉS de marcar sys.frozen

    _ensure_models_copied(settings.MODELS_DIR)
    os.makedirs(settings.FACES_DIR, exist_ok=True)
    os.makedirs(settings.SNAPSHOTS_DIR, exist_ok=True)

    # object_detector.py carga el modelo de YOLO como YOLO("yolov8n.pt"), una ruta
    # relativa -- ultralytics lo busca primero en el directorio de trabajo actual.
    # Nos paramos en la carpeta de datos del usuario (donde ya copiamos el .pt justo
    # arriba) para que lo encuentre ahí y no intente bajarlo de internet.
    os.chdir(settings.MODELS_DIR)

    import uvicorn

    from app.main import app
    from app import phone_home

    phone_home.start_background_sync()

    # "/activation" se salta solo (redirige a /login) en builds sin servidor
    # central configurado -- así este cambio no afecta nada de cómo ya venía
    # funcionando esto para builds sin CENTRAL_SERVER_URL.
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8000/activation")).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
