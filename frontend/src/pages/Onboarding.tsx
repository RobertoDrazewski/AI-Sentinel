import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import ZoneCanvasEditor, { Point } from "../components/ZoneCanvasEditor";

const BRAND_LABELS: Record<string, string> = {
  ezviz_hikvision: "EZVIZ / Hikvision",
  dahua: "Dahua",
  reolink: "Reolink",
  dvr_generico_cp_plus_xm: "DVR genérico (CP Plus / XM / chino)",
  onvif_generico: "ONVIF genérico",
  generico: "Otra / no sé"
};

// Plantilla de URL RTSP típica según marca -- la mayoría de los DVR/cámaras
// chinos "sin marca" clonan el protocolo de Dahua, por eso ese patrón cubre
// bastante más que sólo las Dahua de verdad.
const RTSP_HELP: Record<string, { template: string; note: string }> = {
  ezviz_hikvision: {
    template: "rtsp://usuario:contraseña@IP:554/Streaming/Channels/101",
    note: '"101" es el canal 1 en calidad principal (102 = calidad más baja/más liviana). Si tenés un DVR con varias cámaras, el canal 2 sería 201, el 3 sería 301, etc.'
  },
  dahua: {
    template: "rtsp://usuario:contraseña@IP:554/cam/realmonitor?channel=1&subtype=0",
    note: '"channel=1" es la cámara 1 (channel=2 la segunda, etc). "subtype=0" es calidad principal, "subtype=1" es la liviana.'
  },
  reolink: {
    template: "rtsp://usuario:contraseña@IP:554/h264Preview_01_main",
    note: '"01" es el número de cámara. "_main" es calidad principal, "_sub" es la liviana.'
  },
  dvr_generico_cp_plus_xm: {
    template: "rtsp://usuario:contraseña@IP:554/cam/realmonitor?channel=1&subtype=0",
    note: "La mayoría de estos DVR \"sin marca\" clonan el protocolo Dahua por dentro, así que probá primero con este formato. Si no conecta, buscá en Google \"<marca que figura en la caja/sticker> rtsp url\" -- casi siempre alguien ya lo publicó."
  },
  onvif_generico: {
    template: "rtsp://usuario:contraseña@IP:554/onvif1",
    note: 'Si esto no funciona, instalá (en una compu) "ONVIF Device Manager" (gratis) conectado a la misma red: detecta la cámara sola y te muestra la URL RTSP exacta para copiar y pegar acá.'
  },
  generico: {
    template: "rtsp://usuario:contraseña@IP:554/...",
    note: "No hay un formato único -- depende de la marca real que tenga adentro. Mirá el sticker/manual del equipo, o buscá en Google el modelo exacto + \"rtsp url\"."
  }
};

type Step = 1 | 2 | 3 | 4 | 5;

export default function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);

  // --- Paso 1: cámara ---
  const [name, setName] = useState("Cámara porche");
  const [brand, setBrand] = useState("ezviz_hikvision");
  const [rtspUrl, setRtspUrl] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string; snapshot_base64?: string } | null>(
    null
  );
  const [cameraId, setCameraId] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<string | null>(null);

  // --- Paso 2: zonas ---
  const [zones, setZones] = useState<any[]>([]);
  const [drawingZoneKind, setDrawingZoneKind] = useState<"reja" | "calle" | "custom">("reja");

  // --- Paso 3: rostros ---
  const [faceName, setFaceName] = useState("");
  const [faceFile, setFaceFile] = useState<File | null>(null);
  const [facesUploaded, setFacesUploaded] = useState<string[]>([]);
  const [faceMsg, setFaceMsg] = useState<string | null>(null);

  // --- Paso 4: telegram ---
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [telegramMsg, setTelegramMsg] = useState<string | null>(null);

  // --- Paso 5: pánico ---
  const [phone, setPhone] = useState("");

  async function handleTestConnection() {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api.post<any>("/api/cameras/test-connection", { rtsp_url: rtspUrl });
      setTestResult(result);
      if (result.ok && result.snapshot_base64) {
        setSnapshot(`data:image/jpeg;base64,${result.snapshot_base64}`);
      }
    } catch (e: any) {
      setTestResult({ ok: false, message: e.message });
    } finally {
      setTesting(false);
    }
  }

  async function handleSaveCamera() {
    const cam = await api.post<any>("/api/cameras", { name, brand, rtsp_url: rtspUrl });
    setCameraId(cam.id);
    setStep(2);
  }

  async function handleZoneFinish(polygon: Point[]) {
    if (!cameraId) return;
    const zoneName =
      drawingZoneKind === "reja" ? "Reja / entrada" : drawingZoneKind === "calle" ? "Calle / puente" : "Zona";
    const zone = await api.post<any>("/api/zones", {
      camera_id: cameraId,
      name: zoneName,
      kind: drawingZoneKind,
      polygon,
      loiter_seconds: 5,
      detect_people: true,
      detect_vehicles: drawingZoneKind === "calle",
      detect_gate_tamper: drawingZoneKind === "reja"
    });
    setZones((prev) => [...prev, zone]);
  }

  async function handleUploadFace() {
    if (!faceFile || !faceName) return;
    const form = new FormData();
    form.append("file", faceFile);
    try {
      await api.postForm(`/api/faces?name=${encodeURIComponent(faceName)}`, form);
      setFacesUploaded((prev) => [...prev, faceName]);
      setFaceName("");
      setFaceFile(null);
      setFaceMsg(null);
    } catch (e: any) {
      setFaceMsg(e.message);
    }
  }

  async function handleTestTelegram() {
    await api.put("/api/telegram", { bot_token: botToken, chat_id: chatId, enabled: true });
    const res = await api.post<any>("/api/telegram/test");
    setTelegramMsg(res.message);
  }

  async function handleSavePanicContact() {
    await api.put("/api/panic-contact", { phone_number: phone });
    setStep(5 as Step); // ya estamos en 5, esto sólo confirma guardado visualmente
  }

  async function handleFinish() {
    if (cameraId) {
      await api.post(`/api/cameras/${cameraId}/start`);
    }
    navigate("/dashboard");
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      <h1 className="text-xl font-bold text-accent">Configurar nueva cámara</h1>

      <div className="flex gap-2 text-xs">
        {[1, 2, 3, 4, 5].map((s) => (
          <div
            key={s}
            className={`flex-1 h-1.5 rounded-full ${s <= step ? "bg-accent" : "bg-panel2"}`}
          />
        ))}
      </div>

      {step === 1 && (
        <div className="space-y-4 bg-panel p-4 rounded-xl">
          <h2 className="font-semibold">1. Conectá tu cámara o DVR</h2>
          <input
            placeholder="Nombre (ej: Porche, Entrada, Garage)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-panel2 border border-slate-700"
          />
          <select
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-panel2 border border-slate-700"
          >
            {Object.entries(BRAND_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <input
            placeholder="rtsp://usuario:contraseña@192.168.1.38:554/..."
            value={rtspUrl}
            onChange={(e) => setRtspUrl(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-panel2 border border-slate-700 font-mono text-sm"
          />
          <p className="text-xs text-slate-400">
            Pegá la URL RTSP completa de tu cámara/DVR (la que usás en VLC funciona acá también).
            Nunca compartas ni subas esta URL a un repositorio público: tiene tu usuario y contraseña.
          </p>

          <details className="bg-panel2 rounded-lg px-3 py-2 text-xs text-slate-300 group">
            <summary className="cursor-pointer font-medium text-slate-200 list-none flex items-center justify-between">
              ¿Cómo consigo esta URL / la clave de mi cámara?
              <span className="text-slate-500 group-open:rotate-180 transition-transform">▾</span>
            </summary>
            <div className="mt-2 space-y-2">
              <p>
                <strong className="text-slate-200">1. La IP de tu cámara/DVR en tu red de casa:</strong> entrá a la
                página de tu router (normalmente 192.168.1.1 o 192.168.0.1, con el usuario/contraseña que
                trae pegado en una etiqueta) y mirá la lista de "dispositivos conectados" -- ahí vas a ver el
                nombre y la IP de tu cámara/DVR. También suele verse en la app del celular que ya usás para
                mirar la cámara (en "Configuración de red" o "Info del dispositivo").
              </p>
              <p>
                <strong className="text-slate-200">2. El usuario y la contraseña:</strong> son los mismos que
                usás para entrar a la app de la cámara o a su página web -- si nunca los cambiaste, probá con
                admin / admin o mirá el sticker del equipo.
              </p>
              <p>
                <strong className="text-slate-200">3. Armá la URL con ese formato:</strong>
              </p>
              <code className="block bg-panel px-2 py-1.5 rounded text-accent break-all">
                {RTSP_HELP[brand]?.template || RTSP_HELP.generico.template}
              </code>
              <p>{RTSP_HELP[brand]?.note || RTSP_HELP.generico.note}</p>
              <p className="text-slate-400">
                Reemplazá sólo "usuario", "contraseña" e "IP" por los tuyos, dejá el resto tal cual. Si
                "Probar conexión" te da error, el motivo más común es la IP o el canal mal puestos -- probá
                primero esa URL en VLC (Medio → Abrir ubicación de red) para confirmar que conecta ahí antes
                de pegarla acá.
              </p>
            </div>
          </details>
          <button
            onClick={handleTestConnection}
            disabled={testing || !rtspUrl}
            className="px-4 py-2 rounded-lg bg-panel2 hover:bg-slate-700 disabled:opacity-40"
          >
            {testing ? "Probando..." : "Probar conexión"}
          </button>

          {testResult && (
            <div className={`text-sm ${testResult.ok ? "text-ok" : "text-danger"}`}>{testResult.message}</div>
          )}

          {snapshot && (
            <img src={snapshot} alt="preview" className="rounded-lg w-full" />
          )}

          <button
            onClick={handleSaveCamera}
            disabled={!testResult?.ok}
            className="w-full py-2 rounded-lg bg-accent text-slate-900 font-semibold disabled:opacity-40"
          >
            Guardar y continuar
          </button>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4 bg-panel p-4 rounded-xl">
          <h2 className="font-semibold">2. Marcá tus zonas de interés</h2>
          <p className="text-xs text-slate-400">
            Por ejemplo: la zona de la reja/puerta (para detectar manipulación y permanencia) y la
            zona de calle/puente (para detectar vehículos o motos detenidas).
          </p>
          <div className="flex gap-2 text-sm">
            {(["reja", "calle", "custom"] as const).map((k) => (
              <button
                key={k}
                onClick={() => setDrawingZoneKind(k)}
                className={`px-3 py-1.5 rounded-lg ${
                  drawingZoneKind === k ? "bg-accent text-slate-900" : "bg-panel2"
                }`}
              >
                {k === "reja" ? "Reja/puerta" : k === "calle" ? "Calle/puente" : "Otra zona"}
              </button>
            ))}
          </div>
          {snapshot && <ZoneCanvasEditor imageSrc={snapshot} onFinish={handleZoneFinish} />}
          <div className="text-sm text-slate-300">
            Zonas guardadas: {zones.length === 0 ? "ninguna todavía" : zones.map((z) => z.name).join(", ")}
          </div>
          <button
            onClick={() => setStep(3)}
            className="w-full py-2 rounded-lg bg-accent text-slate-900 font-semibold"
          >
            Continuar
          </button>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4 bg-panel p-4 rounded-xl">
          <h2 className="font-semibold">3. Cargá fotos de familiares (opcional)</h2>
          <p className="text-xs text-slate-400">
            Cualquier rostro que no coincida con estas fotos se va a marcar como posible intruso.
          </p>
          <input
            placeholder="Nombre de la persona"
            value={faceName}
            onChange={(e) => setFaceName(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-panel2 border border-slate-700"
          />
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setFaceFile(e.target.files?.[0] || null)}
            className="w-full text-sm"
          />
          {faceMsg && <p className="text-xs text-danger">{faceMsg}</p>}
          <button
            onClick={handleUploadFace}
            disabled={!faceFile || !faceName}
            className="px-4 py-2 rounded-lg bg-panel2 hover:bg-slate-700 disabled:opacity-40"
          >
            Agregar rostro
          </button>
          {facesUploaded.length > 0 && (
            <p className="text-xs text-ok">Cargados: {facesUploaded.join(", ")}</p>
          )}
          <button
            onClick={() => setStep(4)}
            className="w-full py-2 rounded-lg bg-accent text-slate-900 font-semibold"
          >
            Continuar
          </button>
        </div>
      )}

      {step === 4 && (
        <div className="space-y-4 bg-panel p-4 rounded-xl">
          <h2 className="font-semibold">4. Bot de Telegram para las alertas</h2>
          <p className="text-xs text-slate-400">
            Creá un bot con @BotFather, pegá el token acá, y el chat_id al que querés que lleguen las
            fotos y alertas (puede ser tu chat personal o un grupo).
          </p>

          <details className="bg-panel2 rounded-lg px-3 py-2 text-xs text-slate-300 group">
            <summary className="cursor-pointer font-medium text-slate-200 list-none flex items-center justify-between">
              ¿Cómo consigo el token y el Chat ID?
              <span className="text-slate-500 group-open:rotate-180 transition-transform">▾</span>
            </summary>
            <ol className="mt-2 space-y-2 list-decimal list-inside">
              <li>
                En Telegram, buscá el usuario <strong className="text-slate-200">@BotFather</strong> (el bot
                oficial para crear bots) y escribile <code className="text-accent">/newbot</code>.
              </li>
              <li>
                Te va a pedir un nombre para mostrar y un usuario único que termine en "bot" (ej:
                "porche_alerta_bot"). Al terminar te da un <strong className="text-slate-200">token</strong>
                : una cadena larga tipo <code className="text-accent">123456789:AAExxxxxxxxxxxxxxxxxxxxxxx</code>.
                Pegalo en "Token del bot" de acá arriba.
              </li>
              <li>
                Buscá a tu bot nuevo por el usuario que le pusiste y escribile cualquier mensaje (ej: "hola") --
                si no le escribís primero, Telegram no te va a dejar enviarle nada desde afuera.
              </li>
              <li>
                Abrí esta dirección en el navegador, reemplazando TU_TOKEN por el token de arriba:
                <br />
                <code className="block bg-panel px-2 py-1.5 rounded text-accent break-all mt-1">
                  https://api.telegram.org/botTU_TOKEN/getUpdates
                </code>
                Ahí vas a ver un bloque con <code className="text-accent">"chat":{"{"}"id":123456789{"}"}</code>
                -- ese número es tu <strong className="text-slate-200">Chat ID</strong>. Pegalo arriba.
              </li>
              <li>
                Si preferís que las alertas lleguen a un grupo en vez de a tu chat personal: creá el grupo,
                agregá al bot como miembro, escribí cualquier mensaje en el grupo y repetí el paso anterior --
                el Chat ID de un grupo suele ser un número negativo (ej: -1001234567890).
              </li>
            </ol>
          </details>

          <input
            placeholder="Token del bot"
            value={botToken}
            onChange={(e) => setBotToken(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-panel2 border border-slate-700 font-mono text-sm"
          />
          <input
            placeholder="Chat ID"
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-panel2 border border-slate-700 font-mono text-sm"
          />
          <button
            onClick={handleTestTelegram}
            disabled={!botToken || !chatId}
            className="px-4 py-2 rounded-lg bg-panel2 hover:bg-slate-700 disabled:opacity-40"
          >
            Enviar mensaje de prueba
          </button>
          {telegramMsg && <p className="text-xs text-slate-300">{telegramMsg}</p>}
          <button
            onClick={() => setStep(5)}
            className="w-full py-2 rounded-lg bg-accent text-slate-900 font-semibold"
          >
            Continuar
          </button>
        </div>
      )}

      {step === 5 && (
        <div className="space-y-4 bg-panel p-4 rounded-xl">
          <h2 className="font-semibold">5. Contacto para el botón de pánico</h2>
          <p className="text-xs text-slate-400">
            El botón de pánico envía una alerta crítica inmediata y abre el marcador para llamar al
            911. Este contacto queda guardado como referencia adicional en tus alertas críticas.
          </p>
          <input
            placeholder="Teléfono de referencia (ej: +549261xxxxxxx)"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-panel2 border border-slate-700"
          />
          <button onClick={handleSavePanicContact} className="px-4 py-2 rounded-lg bg-panel2 hover:bg-slate-700">
            Guardar contacto
          </button>
          <button
            onClick={handleFinish}
            className="w-full py-2 rounded-lg bg-accent text-slate-900 font-semibold"
          >
            Finalizar e iniciar monitoreo
          </button>
        </div>
      )}
    </div>
  );
}
