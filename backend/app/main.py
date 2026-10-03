import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers import admin, agent, alerts, auth, cameras, faces, stream, subscription, telegram, zones

# Estas carpetas tienen que existir ANTES de montar StaticFiles más abajo (el mount se
# evalúa al importar el módulo, antes de que corra el evento de startup).
os.makedirs(settings.FACES_DIR, exist_ok=True)
os.makedirs(settings.SNAPSHOTS_DIR, exist_ok=True)
os.makedirs(settings.MODELS_DIR, exist_ok=True)

app = FastAPI(title="AI Sentinel by Puma Code", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    # Además del origen configurado, permitimos cualquier IP de red local (celular
    # conectado al mismo wifi entrando por http://192.168.x.x:5173, por ejemplo) y
    # cualquier dirección/nombre de Tailscale (celular entrando de lejos por VPN
    # personal, ej. http://100.x.x.x:5173 o http://tu-mac.tailXXXX.ts.net:5173) en
    # cualquier puerto. Sigue siendo sólo redes privadas/VPN propia, nunca internet
    # público en general.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9.-]+\.ts\.net):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(zones.router)
app.include_router(faces.router)
app.include_router(alerts.router)
app.include_router(telegram.router)
app.include_router(subscription.router)
app.include_router(admin.router)
app.include_router(agent.router)
app.include_router(stream.router)

# Fotos de rostros conocidos y snapshots de alertas servidas directo (quedan detrás
# del token igualmente porque el frontend las pide con la URL que devuelve la API).
app.mount("/media/faces", StaticFiles(directory=settings.FACES_DIR), name="faces")
app.mount("/media/snapshots", StaticFiles(directory=settings.SNAPSHOTS_DIR), name="snapshots")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "centinela-ia-backend"}


# --- Frontend compilado (sólo en producción) ---
# En desarrollo local (run.sh) esta carpeta no existe -- el frontend lo sirve Vite
# aparte en :5173 -- así que todo esto queda inactivo y no cambia nada del flujo
# que ya usás en tu máquina. En un deploy de un solo servicio (Railway, por
# ejemplo) el Dockerfile compila el frontend y lo copia acá, y FastAPI termina
# sirviendo todo desde el mismo dominio: sin CORS entre front y back, y sin tener
# que correr/pagar dos servicios separados sólo para probar.
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "static_frontend")
if os.path.isdir(_FRONTEND_DIST):
    app.mount(
        "/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="frontend-assets"
    )

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # No pisa ninguna ruta de /api ni /media: FastAPI ya matcheó esos
        # routers/mounts más arriba (se registraron antes), así que esta ruta
        # catch-all sólo se evalúa cuando ninguno de los anteriores respondió.
        # Si el path pide un archivo real del build (ej. favicon, manifest), lo
        # servimos tal cual; si no, devolvemos index.html para que React Router
        # resuelva la ruta del lado del cliente (recargar /dashboard a mano, etc).
        candidate = os.path.join(_FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))
