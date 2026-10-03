import { useEffect, useState } from "react";
import { api } from "../api/client";

interface Subscription {
  status: string;
  amount_ars: number;
  mp_preference_id?: string;
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
  const [summary, setSummary] = useState<AccountSummary | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const data = await api.get<AccountSummary>("/api/subscription/summary");
    setSummary(data);
  }

  useEffect(() => {
    load();
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

  if (!summary) return <div className="p-6 text-slate-400">Cargando...</div>;

  const sub = summary.subscription;

  return (
    <div className="max-w-md mx-auto p-6 space-y-5">
      <h1 className="text-xl font-bold text-accent">Mi cuenta</h1>

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

      <button
        onClick={handleSubscribe}
        className="w-full py-2 rounded-lg bg-accent text-slate-900 font-semibold"
      >
        Pagar con Mercado Pago
      </button>

      <button
        onClick={handleSimulate}
        className="w-full py-2 rounded-lg bg-panel2 text-slate-300 text-sm"
      >
        (Dev) Simular pago aprobado sin Mercado Pago
      </button>

      {message && <p className="text-sm text-slate-300">{message}</p>}

      <p className="text-xs text-slate-500">
        Para probar el pago real necesitás cargar tu MP_ACCESS_TOKEN de prueba en el .env del backend.
        El webhook de confirmación sólo funciona con una URL pública (ngrok/cloudflared) mientras
        desarrollás en localhost.
      </p>

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
