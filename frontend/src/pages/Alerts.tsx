import { useEffect, useState } from "react";
import { api } from "../api/client";
import AlertCard, { AlertItem } from "../components/AlertCard";

export default function Alerts() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    const data = await api.get<AlertItem[]>("/api/alerts");
    setAlerts(data);
    setLoading(false);
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="max-w-7xl mx-auto p-4">
      <h1 className="text-xl font-bold text-accent mb-4">Alertas recientes</h1>
      {loading && <p className="text-slate-400">Cargando...</p>}
      {!loading && alerts.length === 0 && (
        <p className="text-slate-400">Todavía no hay alertas registradas.</p>
      )}
      {/* En pantallas anchas se acomodan en columnas en vez de una sola lista
          larga y angosta -- así se aprovecha el ancho en vez de dejar todo el
          espacio de los costados vacío. */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {alerts.map((a) => (
          <AlertCard key={a.id} alert={a} />
        ))}
      </div>
    </div>
  );
}
