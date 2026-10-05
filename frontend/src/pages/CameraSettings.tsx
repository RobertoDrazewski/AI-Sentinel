import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, mediaUrl } from "../api/client";
import { useAuth } from "../context/AuthContext";
import ZoneCanvasEditor, { Point } from "../components/ZoneCanvasEditor";

interface Camera {
  id: number;
  name: string;
  brand: string;
  rtsp_url: string;
  status: string;
  is_monitoring: boolean;
}

interface Zone {
  id: number;
  camera_id: number;
  name: string;
  kind: string;
  polygon: Point[];
  loiter_seconds: number;
  detect_vehicles: boolean;
  detect_people: boolean;
  detect_gate_tamper: boolean;
  vehicle_stop_seconds: number;
  blocks_exit: boolean;
}

interface KnownFace {
  id: number;
  name: string;
  image_path: string;
}

// Fase 1 del pedido de Roberto: nombrar cada tipo de zona por lo que detecta
// (vocabulario de seguridad/actividad), no por la metáfora física -- el valor
// interno ("reja"/"calle"/"timbre"/"custom") sigue igual (lo usa la lógica de
// camera_worker.py y ya está guardado en zonas existentes), sólo cambia el
// texto que ve el usuario.
const KIND_LABELS: Record<string, string> = {
  reja: "Detecta movimiento",
  calle: "Detecta vehículos",
  custom: "Detecta personas",
  timbre: "Detecta un gesto corto"
};

function defaultZoneName(kind: "reja" | "calle" | "custom" | "timbre", blocksExit: boolean) {
  if (kind === "reja") return "Reja / entrada";
  if (kind === "calle") return blocksExit ? "Salida de garage" : "Calle / puente";
  if (kind === "timbre") return "Timbre";
  return "Zona";
}

export default function CameraSettings() {
  const { id } = useParams();
  const cameraId = Number(id);
  const navigate = useNavigate();
  const { user } = useAuth();
  const isBusinessMode = user?.account_mode === "negocio";

  const [camera, setCamera] = useState<Camera | null>(null);
  const [name, setName] = useState("");
  const [savingName, setSavingName] = useState(false);

  const [zones, setZones] = useState<Zone[]>([]);
  const [addingZone, setAddingZone] = useState(false);
  const [zoneSnapshot, setZoneSnapshot] = useState<string | null>(null);
  const [zoneKind, setZoneKind] = useState<"reja" | "calle" | "custom" | "timbre">("reja");
  const [zoneLoading, setZoneLoading] = useState(false);
  const [zoneError, setZoneError] = useState<string | null>(null);
  const [zoneVehicleStopSeconds, setZoneVehicleStopSeconds] = useState(60);
  const [zoneBlocksExit, setZoneBlocksExit] = useState(false);
  const [zoneNameInput, setZoneNameInput] = useState(defaultZoneName("reja", false));
  const [editingZoneId, setEditingZoneId] = useState<number | null>(null);
  const [editingZoneName, setEditingZoneName] = useState("");

  const [faces, setFaces] = useState<KnownFace[]>([]);
  const [faceName, setFaceName] = useState("");
  const [faceFile, setFaceFile] = useState<File | null>(null);
  const [faceMsg, setFaceMsg] = useState<string | null>(null);
  const [capturingFace, setCapturingFace] = useState(false);

  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [telegramMsg, setTelegramMsg] = useState<string | null>(null);

  const [phone, setPhone] = useState("");
  const [panicMsg, setPanicMsg] = useState<string | null>(null);

  async function loadAll() {
    const [cam, zonesData, facesData, tgConfig, panicContact] = await Promise.all([
      api.get<Camera>(`/api/cameras/${cameraId}`),
      api.get<Zone[]>(`/api/zones/by-camera/${cameraId}`),
      api.get<KnownFace[]>("/api/faces"),
      api.get<any>("/api/telegram"),
      api.get<any>("/api/panic-contact")
    ]);
    setCamera(cam);
    setName(cam.name);
    setZones(zonesData);
    setFaces(facesData);
    setBotToken(tgConfig.bot_token || "");
    setChatId(tgConfig.chat_id || "");
    setPhone(panicContact.phone_number || "");
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraId]);

  async function handleSaveName() {
    setSavingName(true);
    try {
      await api.put(`/api/cameras/${cameraId}`, { name });
      await loadAll();
    } finally {
      setSavingName(false);
    }
  }

  async function handleDeleteCamera() {
    if (!confirm(`¿Eliminar "${camera?.name}"? Esto borra también sus zonas y alertas.`)) return;
    await api.del(`/api/cameras/${cameraId}`);
    navigate("/dashboard");
  }

  async function handleStartAddZone() {
    setZoneError(null);
    setZoneLoading(true);
    try {
      const result = await api.get<any>(`/api/cameras/${cameraId}/snapshot`);
      if (!result.ok || !result.snapshot_base64) {
        setZoneError(result.message || "No se pudo sacar una foto de la cámara ahora mismo.");
        return;
      }
      setZoneSnapshot(`data:image/jpeg;base64,${result.snapshot_base64}`);
      setZoneKind("reja");
      setZoneNameInput(defaultZoneName("reja", false));
      setZoneVehicleStopSeconds(60);
      setZoneBlocksExit(false);
      setAddingZone(true);
    } finally {
      setZoneLoading(false);
    }
  }

  async function handleZoneFinish(polygon: Point[]) {
    const zoneName = zoneNameInput.trim() || defaultZoneName(zoneKind, zoneBlocksExit);
    await api.post("/api/zones", {
      camera_id: cameraId,
      name: zoneName,
      kind: zoneKind,
      polygon,
      loiter_seconds: 5,
      detect_people: zoneKind !== "calle" && zoneKind !== "timbre",
      detect_vehicles: zoneKind === "calle",
      detect_gate_tamper: zoneKind === "reja" || zoneKind === "timbre",
      vehicle_stop_seconds: zoneVehicleStopSeconds,
      blocks_exit: zoneKind === "calle" && zoneBlocksExit
    });
    setAddingZone(false);
    setZoneSnapshot(null);
    setZoneVehicleStopSeconds(60);
    setZoneBlocksExit(false);
    await loadAll();
  }

  async function handleDeleteZone(zoneId: number) {
    await api.del(`/api/zones/${zoneId}`);
    await loadAll();
  }

  async function handleUpdateZone(
    zoneId: number,
    patch: {
      name?: string;
      vehicle_stop_seconds?: number;
      blocks_exit?: boolean;
      detect_people?: boolean;
      detect_vehicles?: boolean;
      detect_gate_tamper?: boolean;
    }
  ) {
    await api.put(`/api/zones/${zoneId}`, patch);
    await loadAll();
  }

  function startEditingZoneName(z: Zone) {
    setEditingZoneId(z.id);
    setEditingZoneName(z.name);
  }

  async function saveZoneName(zoneId: number) {
    const trimmed = editingZoneName.trim();
    setEditingZoneId(null);
    if (!trimmed) return;
    await handleUpdateZone(zoneId, { name: trimmed });
  }

  async function handleUploadFace() {
    if (!faceFile || !faceName) return;
    const form = new FormData();
    form.append("file", faceFile);
    try {
      await api.postForm(`/api/faces?name=${encodeURIComponent(faceName)}`, form);
      setFaceName("");
      setFaceFile(null);
      setFaceMsg(null);
      await loadAll();
    } catch (e: any) {
      setFaceMsg(e.message);
    }
  }

  async function handleDeleteFace(faceId: number) {
    await api.del(`/api/faces/${faceId}`);
    await loadAll();
  }

  async function handleCaptureFaceFromCamera() {
    if (!faceName) return;
    setCapturingFace(true);
    setFaceMsg(null);
    try {
      await api.post(
        `/api/faces/from-camera?camera_id=${cameraId}&name=${encodeURIComponent(faceName)}`
      );
      setFaceName("");
      await loadAll();
    } catch (e: any) {
      setFaceMsg(e.message);
    } finally {
      setCapturingFace(false);
    }
  }

  async function handleTestTelegram() {
    await api.put("/api/telegram", { bot_token: botToken, chat_id: chatId, enabled: true });
    const res = await api.post<any>("/api/telegram/test");
    setTelegramMsg(res.message);
  }

  async function handleSavePanicContact() {
    await api.put("/api/panic-contact", { phone_number: phone });
    setPanicMsg("Contacto guardado.");
    setTimeout(() => setPanicMsg(null), 3000);
  }

  if (!camera) return <div className="p-6 text-slate-400">Cargando...</div>;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-accent">Configuración: {camera.name}</h1>
        <Link to="/dashboard" className="text-sm text-slate-400 hover:text-slate-200">
          ← Volver
        </Link>
      </div>

      {/* --- Datos de la cámara --- */}
      <section className="bg-panel p-4 rounded-xl space-y-3">
        <h2 className="font-semibold">Cámara</h2>
        <div className="flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 px-3 py-2 rounded-lg bg-panel2 border border-slate-700"
          />
          <button
            onClick={handleSaveName}
            disabled={savingName || name === camera.name}
            className="px-4 py-2 rounded-lg bg-accent text-slate-900 font-semibold disabled:opacity-40"
          >
            Guardar
          </button>
        </div>
        <p className="text-xs text-slate-400">
          Estado actual: <span className="text-slate-300">{camera.status}</span> · marca:{" "}
          {camera.brand}
        </p>
        <button onClick={handleDeleteCamera} className="text-sm text-danger hover:underline">
          Eliminar esta cámara
        </button>
      </section>

      {/* En pantallas anchas, Zonas y Familiares van lado a lado (en vez de
          apilados en una columna angosta) para aprovechar el ancho de la
          pantalla -- items-start para que una columna más corta no se estire
          para igualar la otra. */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* --- Zonas --- */}
        <section className="bg-panel p-4 rounded-xl space-y-3">
          <h2 className="font-semibold">Zonas</h2>
          {zones.length === 0 && <p className="text-sm text-slate-400">Todavía no tenés zonas marcadas.</p>}
          {zones.map((z) => (
            <div
              key={z.id}
              className={`rounded-lg px-3 py-2 space-y-2 ${
                z.blocks_exit ? "bg-danger/10 border border-danger/40" : "bg-panel2"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  {editingZoneId === z.id ? (
                    <div className="flex items-center gap-1.5">
                      <input
                        autoFocus
                        value={editingZoneName}
                        onChange={(e) => setEditingZoneName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveZoneName(z.id);
                          if (e.key === "Escape") setEditingZoneId(null);
                        }}
                        onBlur={() => saveZoneName(z.id)}
                        className="px-2 py-1 rounded bg-panel border border-slate-700 text-sm w-40"
                      />
                    </div>
                  ) : (
                    <p
                      className="text-sm font-medium cursor-pointer hover:underline decoration-dotted"
                      title="Click para cambiarle el nombre"
                      onClick={() => startEditingZoneName(z)}
                    >
                      {z.blocks_exit && "🔴 "}
                      {z.name} <span className="text-slate-500">✎</span>
                    </p>
                  )}
                  <p className="text-xs text-slate-400">
                    {KIND_LABELS[z.kind] || z.kind}
                    {z.detect_people && " · presencia y permanencia"}
                    {z.detect_vehicles && ` · objetos detenidos >${z.vehicle_stop_seconds}s`}
                    {z.detect_gate_tamper && z.kind === "timbre" && " · detecta movimiento"}
                    {z.detect_gate_tamper && z.kind !== "timbre" && " · detecta movimiento (reja/puerta)"}
                    {z.detect_people && ` · ${z.loiter_seconds}s`}
                  </p>
                </div>
                <button onClick={() => handleDeleteZone(z.id)} className="text-xs text-danger hover:underline flex-shrink-0">
                  Borrar
                </button>
              </div>

              {/* Qué vigila esta zona. Independiente del tipo con el que se creó --
                  así una zona "Otra zona"/"Calle" puede activar vehículos, o una
                  "Reja" puede dejar sólo el movimiento sin permanencia de personas,
                  sin tener que borrarla y crearla de nuevo con otro tipo. */}
              <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300">
                <label className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={z.detect_people}
                    onChange={(e) => handleUpdateZone(z.id, { detect_people: e.target.checked })}
                  />
                  Detecta personas (presencia y permanencia)
                </label>
                <label className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={z.detect_vehicles}
                    onChange={(e) => handleUpdateZone(z.id, { detect_vehicles: e.target.checked })}
                  />
                  Detecta vehículos (objetos detenidos)
                </label>
                <label className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={z.detect_gate_tamper}
                    onChange={(e) => handleUpdateZone(z.id, { detect_gate_tamper: e.target.checked })}
                  />
                  Detecta movimiento (reja/puerta)
                </label>
              </div>

              {z.detect_vehicles && (
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300 pt-1 border-t border-slate-700/60">
                  <label className="flex items-center gap-1.5">
                    Avisar si un vehículo está parado más de
                    <input
                      type="number"
                      min={1}
                      value={z.vehicle_stop_seconds}
                      onChange={(e) =>
                        handleUpdateZone(z.id, {
                          vehicle_stop_seconds: Number(e.target.value) || 1
                        })
                      }
                      className="w-16 px-2 py-1 rounded bg-panel border border-slate-700 text-center"
                    />
                    segundos
                  </label>
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={z.blocks_exit}
                      onChange={(e) => handleUpdateZone(z.id, { blocks_exit: e.target.checked })}
                    />
                    Tapa la salida del garage (alarma roja)
                  </label>
                </div>
              )}
            </div>
          ))}

          {!addingZone && (
            <button
              onClick={handleStartAddZone}
              disabled={zoneLoading}
              className="px-4 py-2 rounded-lg bg-panel2 hover:bg-slate-700 text-sm disabled:opacity-40"
            >
              {zoneLoading ? "Sacando foto de la cámara..." : "+ Agregar zona nueva"}
            </button>
          )}
          {zoneError && <p className="text-xs text-danger">{zoneError}</p>}

          {addingZone && zoneSnapshot && (
            <div className="space-y-3 pt-2 border-t border-slate-700">
              <div className="flex gap-2 text-sm flex-wrap">
                {(["reja", "calle", "timbre", "custom"] as const).map((k) => (
                  <button
                    key={k}
                    onClick={() => {
                      setZoneKind(k);
                      // Si todavía no tocó el nombre a mano, le sugerimos uno según el tipo.
                      if (!editingZoneId && (zoneNameInput === defaultZoneName(zoneKind, zoneBlocksExit) || !zoneNameInput)) {
                        setZoneNameInput(defaultZoneName(k, zoneBlocksExit));
                      }
                    }}
                    className={`px-3 py-1.5 rounded-lg ${
                      zoneKind === k ? "bg-accent text-slate-900" : "bg-panel2"
                    }`}
                  >
                    {KIND_LABELS[k]}
                  </button>
                ))}
              </div>

              <label className="flex items-center gap-2 text-sm">
                Nombre de la zona
                <input
                  value={zoneNameInput}
                  onChange={(e) => setZoneNameInput(e.target.value)}
                  placeholder={defaultZoneName(zoneKind, zoneBlocksExit)}
                  className="flex-1 px-3 py-2 rounded-lg bg-panel2 border border-slate-700"
                />
              </label>

              {zoneKind === "timbre" && (
                <p className="text-xs text-slate-400 bg-panel2 rounded-lg px-3 py-2">
                  Dibujá una zona chica y ajustada justo sobre el timbre/puerta. Cualquier mano o
                  movimiento que la cruce te manda un aviso de "tocaron el timbre" — no hace falta
                  que sea una persona entera, por eso sirve para una mano acercándose.
                </p>
              )}

              {zoneKind === "calle" && (
                <div className="bg-panel2 rounded-lg p-3 space-y-2 text-sm">
                  <label className="flex items-center gap-2">
                    Avisarme si un auto o moto se queda parado más de
                    <input
                      type="number"
                      min={1}
                      value={zoneVehicleStopSeconds}
                      onChange={(e) => setZoneVehicleStopSeconds(Number(e.target.value) || 1)}
                      className="w-16 px-2 py-1 rounded bg-panel border border-slate-700 text-center"
                    />
                    segundos (60 = 1 minuto)
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={zoneBlocksExit}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        if (zoneNameInput === defaultZoneName("calle", zoneBlocksExit) || !zoneNameInput) {
                          setZoneNameInput(defaultZoneName("calle", checked));
                        }
                        setZoneBlocksExit(checked);
                      }}
                    />
                    Esta zona tapa la salida de mi garage — avisar con alarma roja/urgente
                  </label>
                  {zoneBlocksExit && (
                    <p className="text-xs text-amber-400">
                      Para esta zona te conviene dibujar el triángulo justo frente a tu salida (no toda
                      la calle), y poner pocos segundos arriba — cualquier vehículo parado ahí ya te
                      tapa el paso.
                    </p>
                  )}
                </div>
              )}

              <ZoneCanvasEditor imageSrc={zoneSnapshot} onFinish={handleZoneFinish} />
              <button
                onClick={() => {
                  setAddingZone(false);
                  setZoneSnapshot(null);
                }}
                className="text-xs text-slate-400 hover:underline"
              >
                Cancelar
              </button>
            </div>
          )}
        </section>

        {/* --- Familiares / rostros conocidos --- */}
        <section className="bg-panel p-4 rounded-xl space-y-3">
          <h2 className="font-semibold">
            {isBusinessMode ? "Personal reconocido" : "Familiares reconocidos"}
          </h2>
          <p className="text-xs text-slate-400">
            Vale para todas tus cámaras. Podés subir varias fotos de la misma persona (distintos
            ángulos) para que el reconocimiento sea más confiable.
            {isBusinessMode
              ? " Quien no esté en esta lista se marca como visita no identificada."
              : " Quien no esté en esta lista se marca como intruso."}
          </p>
          {isBusinessMode && (
            <p className="text-xs text-slate-400 bg-panel2/60 rounded-lg px-3 py-2">
              Próximamente: enrolá a tus empleados acá mismo para que el sistema registre
              automáticamente cuándo marcan tarjeta (fichaje con reconocimiento facial).
            </p>
          )}
          <p className="text-xs text-amber-400/90 bg-amber-400/10 rounded-lg px-3 py-2">
            💡 Si subís una selfie del celular y la cámara no te reconoce en vivo, probá sacar la
            foto de referencia con el botón "Capturar desde esta cámara" (parate donde te ve la
            cámara y tocá el botón). Una selfie normal tiene otra luz y otro ángulo que la cámara
            de exterior, y eso puede bajar la similitud por debajo del umbral.
          </p>
          {faces.length > 0 && (
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              {faces.map((f) => (
                <div key={f.id} className="relative group">
                  <img
                    src={mediaUrl(f.image_path)}
                    alt={f.name}
                    className="w-full aspect-square object-cover rounded-lg"
                  />
                  <p className="text-xs text-center mt-1 truncate">{f.name}</p>
                  <button
                    onClick={() => handleDeleteFace(f.id)}
                    className="absolute top-1 right-1 w-5 h-5 rounded-full bg-danger text-white text-xs leading-5 opacity-0 group-hover:opacity-100"
                    title="Borrar"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex flex-col sm:flex-row gap-2 pt-2 border-t border-slate-700">
            <input
              placeholder="Nombre de la persona"
              value={faceName}
              onChange={(e) => setFaceName(e.target.value)}
              className="flex-1 px-3 py-2 rounded-lg bg-panel2 border border-slate-700"
            />
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setFaceFile(e.target.files?.[0] || null)}
              className="text-sm"
            />
            <button
              onClick={handleUploadFace}
              disabled={!faceFile || !faceName}
              className="px-4 py-2 rounded-lg bg-accent text-slate-900 font-semibold disabled:opacity-40"
            >
              Agregar
            </button>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-px bg-slate-700" />
            <span className="text-xs text-slate-500">o</span>
            <div className="flex-1 h-px bg-slate-700" />
          </div>
          <button
            onClick={handleCaptureFaceFromCamera}
            disabled={!faceName || capturingFace}
            className="w-full px-4 py-2 rounded-lg bg-panel2 hover:bg-slate-700 text-sm font-medium disabled:opacity-40"
          >
            {capturingFace
              ? "Sacando foto de la cámara..."
              : "📷 Capturar desde esta cámara ahora (pará frente a ella)"}
          </button>
          {faceMsg && <p className="text-xs text-danger">{faceMsg}</p>}
        </section>
      </div>

      {/* Telegram y Pánico también lado a lado en pantallas anchas. */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* --- Telegram --- */}
        <section className="bg-panel p-4 rounded-xl space-y-3">
          <h2 className="font-semibold">Telegram</h2>

          <details className="bg-panel2 rounded-lg px-3 py-2 text-xs text-slate-300 group">
            <summary className="cursor-pointer font-medium text-slate-200 list-none flex items-center justify-between">
              ¿Cómo consigo el token y el Chat ID?
              <span className="text-slate-500 group-open:rotate-180 transition-transform">▾</span>
            </summary>
            <ol className="mt-2 space-y-2 list-decimal list-inside">
              <li>
                En Telegram, buscá <strong className="text-slate-200">@BotFather</strong> y escribile{" "}
                <code className="text-accent">/newbot</code>. Elegí un nombre y un usuario único terminado en
                "bot". Te da un <strong className="text-slate-200">token</strong> tipo{" "}
                <code className="text-accent">123456789:AAExxxxxxxxxxxxxxxxxxxxxxx</code> — pegalo abajo.
              </li>
              <li>Buscá a tu bot nuevo y escribile cualquier mensaje primero (si no, no te puede escribir él a vos).</li>
              <li>
                Abrí en el navegador (reemplazando TU_TOKEN):
                <br />
                <code className="block bg-panel px-2 py-1.5 rounded text-accent break-all mt-1">
                  https://api.telegram.org/botTU_TOKEN/getUpdates
                </code>
                Buscá <code className="text-accent">"chat":{"{"}"id":123456789{"}"}</code> — ese número es tu{" "}
                <strong className="text-slate-200">Chat ID</strong>.
              </li>
              <li>
                Para un grupo en vez de tu chat personal: agregá el bot al grupo, escribí algo ahí, y repetí el
                paso anterior (el ID de grupo suele ser negativo).
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
            className="px-4 py-2 rounded-lg bg-panel2 hover:bg-slate-700 text-sm disabled:opacity-40"
          >
            Guardar y enviar mensaje de prueba
          </button>
          {telegramMsg && <p className="text-xs text-slate-300">{telegramMsg}</p>}
        </section>

        {/* --- Pánico --- */}
        <section className="bg-panel p-4 rounded-xl space-y-3">
          <h2 className="font-semibold">Contacto de pánico</h2>
          <input
            placeholder="Teléfono de referencia (ej: +549261xxxxxxx)"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-panel2 border border-slate-700"
          />
          <button onClick={handleSavePanicContact} className="px-4 py-2 rounded-lg bg-panel2 hover:bg-slate-700 text-sm">
            Guardar
          </button>
          {panicMsg && <p className="text-xs text-ok">{panicMsg}</p>}
        </section>
      </div>
    </div>
  );
}
