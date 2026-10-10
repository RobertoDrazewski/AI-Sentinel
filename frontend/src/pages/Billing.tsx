import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

interface Subscription {
  status: string;
  amount_ars: number;
  mp_preference_id?: string;
}

interface AgentDevice {
  id: number;
  label: string;
  created_at: string;
  last_seen_at: string | null;
  last_seen_ip: string | null;
}

interface TunnelPublic {
  hostname: string;
  configured: boolean;
}

interface Payment {
  amount_ars: number;
  status: string;
  paid_at: string;
}

interface AccountSummary {
  subscription: Subscription;
  next_due_date: string | null;
  payments_this_month: Payment[];
  faces_recognized_this_month: number;
  critical_alerts_this_month: number;
  total_alerts_this_month: number;
}

const dateFmt = new Intl.DateTimeFormat("es-AR", { day: "numeric", month: "long", year: "numeric" });

export default function Billing() {
  const { user, refreshUser } = useAuth();
  const [summary, setSummary] = useState<AccountSummary | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [devices, setDevices] = useState<AgentDevice[]>([]);
  const [tunnel, setTunnel] = useState<TunnelPublic | null>(null);
  const [showQr, setShowQr] = useState(false);
  const [savingMode, setSavingMode] = useState(false);
  const [resettingTunnel, setResettingTunnel] = useState(false);
  const [tunnelResetMsg, setTunnelResetMsg] = useState<string | null>(null);

  async function load() {
    const data = await api.get<AccountSummary>("/api/subscription/summary");
    setSummary(data);
  }

  async function loadDevices() {
    try {
      const rows = await api.get<AgentDevice[]>("/api/agent/devices");
      setDevices(rows);
    } catch {
      // Esta cuenta puede no tener ningún agente emparejado todavía -- no es un error.
      setDevices([]);
    }
  }

  async function loadTunnel() {
    try {
      const t = await api.get<TunnelPublic>("/api/agent/tunnel/public");
      setTunnel(t);
    } catch {
      setTunnel({ hostname: "", configured: false });
    }
  }

  async function handleRevokeDevice(id: number) {
    await api.del(`/api/agent/devices/${id}`);
    loadDevices();
  }

  // Los túneles creados antes del fix del hostname de dos niveles (ver
  // CLOUDFLARE_TUNNEL_DOMAIN en el backend) quedaron guardados con un
  // subdominio que el SSL de Cloudflare nunca va a cubrir, y _get_or_create_tunnel
  // del backend reusa para siempre lo que ya esté guardado -- esto los borra
  // para que se recreen de cero (con el subdominio bueno) la próxima vez que
  // el agente o este panel los pidan.
  async function handleResetTunnel() {
    setResettingTunnel(true);
    setTunnelResetMsg(null);
    try {
      await api.del("/api/agent/tunnel");
      setShowQr(false);
      await loadTunnel();
      setTunnelResetMsg(
        "Listo. Si el agente de tu PC está prendido, en unos segundos va a tomar la dirección nueva solo."
      );
    } catch {
      setTunnelResetMsg("No se pudo reiniciar el túnel. Probá de nuevo en un momento.");
    } finally {
      setResettingTunnel(false);
    }
  }

  useEffect(() => {
    load();
    loadDevices();
    loadTunnel();
  }, []);

  async function handleSubscribe() {
    const res = await api.post<any>("/api/subscription/create-preference");
    if (!res.ok) {
      setMessage(res.message);
      return;
    }
    window.open(res.sandbox_init_point || res.init_point, "_blank");
  }

  async function handleSimulate() {
    await api.post("/api/subscription/simulate-payment");
    setMessage("Pago simulado: suscripción activada (sólo para desarrollo local).");
    load();
  }

  // Fase 2: Hogar/Negocio sólo cambia el vocabulario que usa el panel (ver
  // CameraSettings.tsx) -- no toca la detección en sí.
  async function handleSetAccountMode(mode: "hogar" | "negocio") {
    if (!user || user.account_mode === mode || savingMode) return;
    setSavingMode(true);
    try {
      await api.put("/api/auth/account-mode", { account_mode: mode });
      await refreshUser();
    } finally {
      setSavingMode(false);
    }
  }

  if (!summary) return <div className="p-6 text-slate-400">Cargando...</div>;

  const sub = summary.subscription;

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <h1 className="text-xl font-bold text-accent">Mi cuenta</h1>

      {/* Fase 2 del pedido de Roberto: separar uso doméstico de negocio/fábrica.
          Por ahora sólo cambia el vocabulario en este panel (ver CameraSettings.tsx),
          no la detección en sí -- la fase siguiente (fichaje de empleados) todavía
          no está construida. */}
      <div className="bg-panel rounded-xl p-4 space-y-3">
        <p className="text-sm text-slate-400">¿Cómo usás AI Sentinel?</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <button
            onClick={() => handleSetAccountMode("hogar")}
            disabled={savingMode}
            className={`text-left rounded-lg p-3 border transition ${
              user?.account_mode === "hogar"
                ? "border-accent bg-panel2/60"
                : "border-slate-700 hover:border-slate-500"
            }`}
          >
            <p className="font-semibold text-sm">🏠 Doméstico / seguridad</p>
            <p className="text-xs text-slate-400 mt-1">
              Familiares reconocidos, alerta de intrusos, cuidado de la casa.
            </p>
          </button>
          <button
            onClick={() => handleSetAccountMode("negocio")}
            disabled={savingMode}
            className={`text-left rounded-lg p-3 border transition ${
              user?.account_mode === "negocio"
                ? "border-accent bg-panel2/60"
                : "border-slate-700 hover:border-slate-500"
            }`}
          >
            <p className="font-semibold text-sm">🏭 Negocios y fábricas</p>
            <p className="text-xs text-slate-400 mt-1">
              Actividad del local/planta, visitas no identificadas. (El fichaje de
              empleados con reconocimiento facial llega en una próxima actualización.)
            </p>
          </button>
        </div>
      </div>

      {/* En pantallas anchas se arma en dos columnas (plan/estadísticas/pagos a
          la izquierda, dispositivos/celular a la derecha) en vez de una sola
          columna larga y angosta en el centro. */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-5">
          <div className="bg-panel rounded-xl p-4 space-y-2">
            <p className="text-sm text-slate-400">Plan mensual</p>
            <p className="text-2xl font-bold">${sub.amount_ars.toLocaleString("es-AR")} ARS / mes</p>
            <p className="text-sm">
              Estado: <span className={sub.status === "activa" ? "text-ok" : "text-warn"}>{sub.status}</span>
            </p>
            {summary.next_due_date && (
              <p className="text-sm text-slate-300">
                Próxima cuota: <span className="font-semibold">{dateFmt.format(new Date(summary.next_due_date))}</span>
              </p>
            )}
          </div>

          <div className="bg-panel rounded-xl p-4 space-y-3">
            <p className="text-sm text-slate-400">Cómo trabajó tu AI Sentinel este mes</p>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-panel2/60 rounded-lg py-3">
                <p className="text-xl font-bold text-accent">{summary.faces_recognized_this_month}</p>
                <p className="text-[11px] text-slate-400 mt-1">Caras reconocidas</p>
              </div>
              <div className="bg-panel2/60 rounded-lg py-3">
                <p className="text-xl font-bold text-accent">{summary.total_alerts_this_month}</p>
                <p className="text-[11px] text-slate-400 mt-1">Alertas totales</p>
              </div>
              <div className="bg-panel2/60 rounded-lg py-3">
                <p className={`text-xl font-bold ${summary.critical_alerts_this_month > 0 ? "text-red-400" : "text-accent"}`}>
                  {summary.critical_alerts_this_month}
                </p>
                <p className="text-[11px] text-slate-400 mt-1">Alertas críticas</p>
              </div>
            </div>
          </div>

          <div className="bg-panel rounded-xl p-4 space-y-2">
            <p className="text-sm text-slate-400">Pagos de este mes</p>
            {summary.payments_this_month.length === 0 ? (
              <p className="text-sm text-slate-500">Todavía no se registró ningún pago este mes.</p>
            ) : (
              <ul className="space-y-1">
                {summary.payments_this_month.map((p, i) => (
                  <li key={i} className="flex justify-between text-sm">
                    <span className="text-slate-300">{dateFmt.format(new Date(p.paid_at))}</span>
                    <span className="font-semibold text-ok">${p.amount_ars.toLocaleString("es-AR")} ARS</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="space-y-5">
          <div className="bg-panel rounded-xl p-4 space-y-3">
            <p className="text-sm text-slate-400">Dispositivos activados</p>
            {devices.length === 0 ? (
              <p className="text-sm text-slate-500">Todavía no activaste el agente en ninguna computadora.</p>
            ) : (
              <ul className="space-y-2">
                {devices.map((d) => (
                  <li key={d.id} className="flex items-center justify-between gap-3 bg-panel2/60 rounded-lg px-3 py-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{d.label}</p>
                      <p className="text-[11px] text-slate-500">
                        {d.last_seen_at
                          ? `Últ. actividad: ${dateFmt.format(new Date(d.last_seen_at))}`
                          : "Sin actividad registrada todavía"}
                        {d.last_seen_ip ? ` · ${d.last_seen_ip}` : ""}
                      </p>
                    </div>
                    <button
                      onClick={() => handleRevokeDevice(d.id)}
                      className="text-xs text-red-400 hover:text-red-300 shrink-0"
                    >
                      Quitar
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-[11px] text-slate-500">
              Hasta 2 computadoras activadas al mismo tiempo por suscripción. Si vendiste o cambiaste de
              equipo, quitalo de aquí antes de activar uno nuevo si ya estás en el tope.
            </p>
          </div>

          <div className="bg-panel rounded-xl p-4 space-y-3">
            <p className="text-sm text-slate-400">Ver desde el celular</p>
            {!tunnel?.configured ? (
              <p className="text-sm text-slate-500">
                Todavía no está disponible el acceso remoto desde el celular para esta cuenta. Mientras
                tanto, las alertas te siguen llegando por Telegram desde cualquier lugar.
              </p>
            ) : showQr ? (
              <div className="flex flex-col items-center gap-3 py-2">
                <div className="bg-white p-3 rounded-lg">
                  <QRCodeSVG value={`https://${tunnel.hostname}`} size={176} />
                </div>
                <p className="text-xs text-slate-400 break-all text-center">https://{tunnel.hostname}</p>
                <button onClick={() => setShowQr(false)} className="text-xs text-slate-500 underline">
                  Ocultar
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowQr(true)}
                className="w-full py-2 rounded-lg bg-panel2 text-slate-100 text-sm font-medium"
              >
                Mostrar código QR
              </button>
            )}
            {tunnel?.configured && (
              <button
                onClick={handleResetTunnel}
                disabled={resettingTunnel}
                className="text-[11px] text-slate-500 hover:text-slate-300 underline disabled:opacity-50"
              >
                {resettingTunnel ? "Reiniciando..." : "¿No carga? Reiniciar túnel"}
              </button>
            )}
            {tunnelResetMsg && <p className="text-[11px] text-slate-400">{tunnelResetMsg}</p>}
          </div>
        </div>
      </div>

      <button
        onClick={handleSubscribe}
        className="w-full py-2 rounded-lg bg-accent text-slate-900 font-semibold"
      >
        Pagar con Mercado Pago
      </button>

      {/* Todo lo de acá abajo es sólo para cuando Roberto está desarrollando
          localmente -- import.meta.env.DEV es false en el build compilado que
          descargan los clientes, así que nunca lo ven. */}
      {import.meta.env.DEV && (
        <>
          <button
            onClick={handleSimulate}
            className="w-full py-2 rounded-lg bg-panel2 text-slate-300 text-sm"
          >
            (Dev) Simular pago aprobado sin Mercado Pago
          </button>
          <p className="text-xs text-slate-500">
            Para probar el pago real necesitás cargar tu MP_ACCESS_TOKEN de prueba en el .env del backend.
            El webhook de confirmación sólo funciona con una URL pública (ngrok/cloudflared) mientras
            desarrollás en localhost.
          </p>
        </>
      )}

      {message && <p className="text-sm text-slate-300">{message}</p>}

      <div className="border border-slate-700 rounded-xl p-4 flex items-start gap-3 bg-panel/40">
        <span className="text-xl leading-none">🔒</span>
        <p className="text-xs text-slate-400">
          Tus fotos y videos nunca salen de tu computadora hacia servidores de Puma Code ni de
          terceros: se guardan sólo en tu propio equipo y las alertas se envían directo a tu
          Telegram privado.
        </p>
      </div>
    </div>
  );
}
