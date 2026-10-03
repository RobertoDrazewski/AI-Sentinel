import { useEffect, useState } from "react";
import { api } from "../api/client";

interface Subscription {
  status: string;
  amount_ars: number;
  mp_preference_id?: string;
}

export default function Billing() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const data = await api.get<Subscription>("/api/subscription");
    setSub(data);
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

  if (!sub) return <div className="p-6 text-slate-400">Cargando...</div>;

  return (
    <div className="max-w-md mx-auto p-6 space-y-4">
      <h1 className="text-xl font-bold text-accent">Suscripción</h1>
      <div className="bg-panel rounded-xl p-4 space-y-2">
        <p className="text-sm text-slate-400">Plan mensual</p>
        <p className="text-2xl font-bold">${sub.amount_ars.toLocaleString("es-AR")} ARS / mes</p>
        <p className="text-sm">
          Estado:{" "}
          <span
            className={sub.status === "activa" ? "text-ok" : "text-warn"}
          >
            {sub.status}
          </span>
        </p>
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
    </div>
  );
}
