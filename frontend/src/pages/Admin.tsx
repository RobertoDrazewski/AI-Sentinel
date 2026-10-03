import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

interface AdminUser {
  id: number;
  email: string;
  business_name?: string | null;
  role: string;
  created_at: string;
  subscription_status: string;
  amount_ars: number;
  next_due_date: string | null;
  cameras_count: number;
  alerts_this_month: number;
}

const STATUS_OPTIONS = ["pendiente", "activa", "vencida", "cancelada"];

const dateFmt = new Intl.DateTimeFormat("es-AR", { day: "numeric", month: "short", year: "numeric" });

const statusColor: Record<string, string> = {
  activa: "text-ok",
  pendiente: "text-warn",
  vencida: "text-red-400",
  cancelada: "text-slate-500",
  sin_suscripcion: "text-slate-500"
};

export default function Admin() {
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);

  async function load() {
    const data = await api.get<AdminUser[]>("/api/admin/users");
    setUsers(data);
  }

  useEffect(() => {
    load();
  }, []);

  // El backend ya devuelve 403 si no sos admin, pero evitamos mostrar la
  // pantalla (y el flash de "Cargando...") a un usuario que no debería verla.
  if (user && user.role !== "admin") return <Navigate to="/dashboard" replace />;

  async function handleStatusChange(userId: number, status: string) {
    setSavingId(userId);
    try {
      await api.put(`/api/admin/users/${userId}/subscription-status`, { status });
      await load();
    } finally {
      setSavingId(null);
    }
  }

  if (!users) return <div className="p-6 text-slate-400">Cargando...</div>;

  return (
    <div className="max-w-3xl mx-auto p-4 sm:p-6 space-y-4">
      <div>
        <h1 className="text-xl font-bold text-accent">Admin</h1>
        <p className="text-sm text-slate-400 mt-1">
          Control de cuentas y suscripciones de esta instalación -- {users.length}{" "}
          {users.length === 1 ? "cuenta" : "cuentas"}.
        </p>
      </div>

      <div className="space-y-3">
        {users.map((u) => (
          <div key={u.id} className="bg-panel rounded-xl p-4 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold text-slate-100 truncate">
                  {u.business_name || u.email}
                </p>
                <p className="text-xs text-slate-500 truncate">{u.email}</p>
              </div>
              {u.role === "admin" && (
                <span className="shrink-0 text-[11px] uppercase tracking-wide bg-accent/15 text-accent px-2 py-1 rounded-full">
                  Admin
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
              <div className="bg-panel2/60 rounded-lg py-2">
                <p className={`text-sm font-semibold ${statusColor[u.subscription_status] || "text-slate-300"}`}>
                  {u.subscription_status}
                </p>
                <p className="text-[10px] text-slate-500 mt-0.5">Suscripción</p>
              </div>
              <div className="bg-panel2/60 rounded-lg py-2">
                <p className="text-sm font-semibold text-slate-200">
                  {u.next_due_date ? dateFmt.format(new Date(u.next_due_date)) : "--"}
                </p>
                <p className="text-[10px] text-slate-500 mt-0.5">Próxima cuota</p>
              </div>
              <div className="bg-panel2/60 rounded-lg py-2">
                <p className="text-sm font-semibold text-slate-200">{u.cameras_count}</p>
                <p className="text-[10px] text-slate-500 mt-0.5">Cámaras</p>
              </div>
              <div className="bg-panel2/60 rounded-lg py-2">
                <p className="text-sm font-semibold text-slate-200">{u.alerts_this_month}</p>
                <p className="text-[10px] text-slate-500 mt-0.5">Alertas del mes</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-400">Cambiar estado:</label>
              <select
                value={u.subscription_status}
                disabled={u.subscription_status === "sin_suscripcion" || savingId === u.id}
                onChange={(e) => handleStatusChange(u.id, e.target.value)}
                className="bg-panel2 border border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-200 disabled:opacity-50"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              {savingId === u.id && <span className="text-xs text-slate-500">Guardando...</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
