# Centinela IA

Prototipo de SaaS de seguridad con IA: convierte cualquier cámara china, DVR o cámara IP que
ya tengas instalada en una "cámara inteligente" con reconocimiento facial, detección de zonas,
alertas por Telegram y botón de pánico. PWA: se instala en el celular agregándola a la pantalla
de inicio, y también se ve bien en un monitor de escritorio.

> ⚠️ Esto es un **MVP para probar en tu red local**, no una versión productiva. Más abajo hay un
> apartado de "Qué falta para producción" con lo importante antes de venderlo como servicio real.

## Qué incluye esta primera versión

- **Multi-tenant básico**: registro/login por email, cada usuario tiene sus propias cámaras.
- **Wizard de alta de cámara**: pegás tu URL RTSP (o armás una desde plantillas por marca),
  probás la conexión, sacás una foto de referencia y dibujás zonas sobre esa foto.
- **Zonas configurables** por polígono: "reja" (permanencia + manipulación), "calle/puente"
  (vehículos detenidos), o zonas genéricas.
- **Reconocimiento facial liviano** (YuNet + SFace de OpenCV, sin dlib): compara contra tus
  fotos de familiares cargadas; lo que no matchea se marca como posible intruso.
- **Detección de personas/vehículos** con YOLOv8n (ultralytics) para la lógica de zonas.
- **Permanencia (loitering)**: sólo avisa si alguien queda parado más de N segundos en una
  zona, ignorando a los que simplemente pasan caminando.
- **Manipulación de reja**: heurística v1 por flujo óptico (ver limitaciones abajo).
- **Alertas por Telegram** configurables por usuario, con foto adjunta.
- **Botón de pánico**: alerta crítica inmediata + abre el marcador del teléfono en `tel:911`
  (ver nota importante más abajo, **no existe una forma de marcar al 911 sin intervención
  humana**).
- **Suscripción Mercado Pago** ($30.000 ARS/mes por defecto, configurable): Checkout Pro +
  webhook, con un endpoint de simulación para probar todo el flujo sin salir de localhost.
- **Streaming en vivo** anotado (zonas + detecciones) vía MJPEG en el dashboard.

## Estructura del proyecto

```
centinela-ia/
  backend/     FastAPI + OpenCV + YOLO (Python)
  frontend/    React + Vite + Tailwind, PWA instalable
  docs/        zonas-ejemplo.json con un punto de partida para tu cámara del porche
```

## Cómo correrlo en tu máquina (localhost)

Importante: el contenedor donde se generó este proyecto **no tiene acceso a tu red local**
(no puede llegar a `192.168.1.38`), así que esto tenés que correrlo en tu propia compu, en la
misma red que la cámara.

### 1. Backend

```bash
cd backend
./run.sh
```

La primera vez, `run.sh` se encarga de: crear el virtualenv, instalar dependencias, copiar
`.env.example` a `.env`, y descargar los modelos de reconocimiento facial (~37MB). Después
levanta la API en `http://localhost:8000` (docs interactivos en `http://localhost:8000/docs`).

La primera vez que uses detección de objetos, `ultralytics` va a descargar `yolov8n.pt`
(~6MB) automáticamente.

Antes de usar Mercado Pago de verdad, completá `MP_ACCESS_TOKEN` en `backend/.env` con tus
credenciales de **TEST**.

### 2. Frontend

En otra terminal:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Abrí `http://localhost:5173`. Para "instalarla" en el celular: abrí esa URL desde el
navegador del teléfono (en la misma red Wi-Fi que tu compu, usando la IP de tu compu en vez
de `localhost`) y usá "Agregar a pantalla de inicio".

### 3. Primeros pasos dentro de la app

1. Registrate con tu email.
2. Te lleva directo al wizard: pegá tu URL RTSP (la misma que usás en VLC), probá la conexión,
   guardá la cámara.
3. Dibujá tus zonas sobre la foto de referencia (en `docs/zonas-ejemplo.json` dejé una
   sugerencia basada en tu encuadre: reja al centro, calle/puente arriba a la derecha donde
   se ve la huella de cemento y estacionan).
4. Cargá fotos de tus familiares (opcional, para que no te marque como intrusos).
5. Configurá tu bot de Telegram (@BotFather) y probá el envío.
6. Cargá un teléfono de referencia para el botón de pánico.
7. "Finalizar e iniciar monitoreo" → te lleva al dashboard con el video en vivo.

## Sobre el botón de pánico y el 911

No existe ninguna API pública (de ningún proveedor, en ningún país) para marcar al 911 de
forma 100% automática sin que una persona confirme la llamada — y hacerlo sin confirmación
sería además un riesgo legal serio por falsas alarmas. Lo que se implementó, como pediste, es
el mismo patrón que usan las apps de alerta de sismos: al mantener presionado el botón, se
registra la alerta crítica (queda en el historial + se manda por Telegram) y **se abre
automáticamente el marcador del teléfono con `tel:911`**. En casi todos los celulares eso deja
el número cargado y listo, y sólo falta un toque en "Llamar" — es la implementación más cercana
a "automático" que el navegador permite.

## Limitaciones conocidas (honestas) de este MVP

- **Manipulación de reja**: es una heurística por flujo óptico (movimiento sostenido en la
  zona), no detección de pose real. Va a generar algún falso positivo/negativo. El próximo paso
  natural si hace falta más precisión es sumar `mediapipe` (manos/pose) acotado a esa zona.
- **Detección de "delivery" por mochila térmica**: no está implementada en esta v1 (YOLO
  detecta "motorcycle" y "person", pero no clasifica mochilas térmicas específicamente). Se
  puede sumar más adelante entrenando/afinando un modelo o con reglas heurísticas adicionales.
- **Tracking**: es un tracker simple por centroide, no DeepSORT. Anda bien para una sola cámara
  con pocos objetos en escena, pero no es robusto con mucha gente/autos superpuestos.
- **Multi-cámara**: el modelo de datos ya soporta varias cámaras por usuario, pero cada una
  corre su propio hilo de procesamiento en el mismo proceso — para producción con varias
  cámaras en simultáneo convendría separar esto en workers/procesos aparte.

## Qué falta para llevarlo a producción (no incluido a propósito en este MVP)

- Subir el video más allá de tu red local: para monitorear desde afuera de casa hace falta que
  el backend esté en un servidor con acceso a tu cámara (VPN hacia tu casa, o reenvío de
  puertos seguro) — exponer RTSP directo a internet sin VPN no es buena idea.
- Reemplazar SQLite por Postgres, y separar el procesamiento de video a un worker aparte
  (Celery/RQ + Redis, o un proceso por cámara) para que escale con más usuarios/cámaras.
- Suscripciones recurrentes reales de Mercado Pago (`preapproval`) en vez de pagos únicos
  repetidos a mano.
- Cifrar la contraseña de la cámara en la base (hoy se guarda en texto plano en tu SQLite
  local — razonable para desarrollo, no para producción multi-usuario).
- HTTPS real + dominio propio para que el webhook de Mercado Pago funcione sin túnel.

## Seguridad: ojo con las credenciales

El `.env` del backend y la URL RTSP (que incluye usuario/contraseña de tu cámara) **nunca se
suben a git** (ya están en `.gitignore`). No pegues tu URL RTSP real en commits, issues, ni la
compartas en texto plano por ningún lado público.
