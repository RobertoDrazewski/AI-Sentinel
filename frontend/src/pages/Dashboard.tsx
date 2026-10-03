import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import LiveStream from "../components/LiveStream";
import PanicButton from "../components/PanicButton";

interface Camera {
  id: number;
  name: string;
  brand: string;
  status: string;
  is_monitoring: boolean;
}

export default function Dashboard() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    const data = await api.get<Camera[]>("/api/cameras");
    setCameras(data);
    setLoading(false);
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000); // refresca estado de conexión
    return () => clearInterval(interval);
  }, []);

  async function toggleMonitoring(cam: Camera) {
    if (cam.is_monitoring) {
      await api.post(`/api/cameras/${cam.id}/stop`);
    } else {
      await api.post(`/api/cameras/${cam.id}/start`);
    }
    load();
  }

  if (loading) return <div className="p-6 text-slate-400">Cargando cámaras...</div>;

  if (cameras.length === 0) {
    return (
      <div className="p-6 text-center space-y-4">
        <p className="text-slate-400">Todavía no configuraste ninguna cámara.</p>
        <Link to="/onboarding" className="inline-block px-4 py-2 rounded-lg bg-accent text-slate-900 font-semibold">
          Configurar mi primera cámara
        </Link>
      </div>
    );
  }

  // Con una sola cámara, que ocupe todo el espacio disponible en vez de quedar
  // encajonada en una columna angosta. Con varias, se reparten en grilla.
  const containerClass =
    cameras.length === 1
      ? "p-4 max-w-6xl mx-auto"
      : cameras.length === 2
      ? "p-4 grid grid-cols-1 lg:grid-cols-2 gap-4"
      : "p-4 grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4";

  return (
    <div className={containerClass}>
      {cameras.map((cam) => (
        <div key={cam.id} className="bg-panel rounded-xl p-3 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">{cam.name}</h3>
            <div className="flex items-center gap-2">
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  cam.status === "conectada"
                    ? "bg-ok/20 text-ok"
                    : cam.status === "error"
                    ? "bg-danger/20 text-danger"
                    : "bg-panel2 text-slate-400"
                }`}
              >
                {cam.status}
              </span>
              <Link
                to={`/camera/${cam.id}/settings`}
                title="Configuración de esta cámara"
                className="w-7 h-7 flex items-center justify-center rounded-lg bg-panel2 hover:bg-slate-700 text-slate-300"
              >
                ⚙️
              </Link>
            </div>
          </div>

          <LiveStream cameraId={cam.id} />

          <div className="flex items-center justify-between gap-3">
            <button
              onClick={() => toggleMonitoring(cam)}
              className={`flex-1 py-2 rounded-lg text-sm font-semibold ${
                cam.is_monitoring ? "bg-panel2 text-slate-300" : "bg-ok text-slate-900"
              }`}
            >
              {cam.is_monitoring ? "Detener monitoreo" : "Iniciar monitoreo"}
            </button>
            <PanicButton cameraId={cam.id} />
          </div>
        </div>
      ))}
    </div>
  );
}
