import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useAppMode } from "../context/AppModeContext";
import { api } from "../api/client";
import logo from "../assets/logo-sentinel.png";

interface TunnelPublic {
  hostname: string;
  configured: boolean;
}

export default function Nav() {
  const { user, logout } = useAuth();
  const { isLocalAgent } = useAppMode();
  const navigate = useNavigate();
  const [tunnel, setTunnel] = useState<TunnelPublic | null>(null);

  // "Panel de control" en el navbar: sólo tiene sentido pedirle el túnel al
  // backend cuando estamos en el portal central (Railway) -- si ya estamos
  // adentro del agente local, las pestañas "Cámaras"/"Alertas" de abajo ya
  // muestran lo mismo, y no hay necesidad de este pedido extra.
  useEffect(() => {
    if (!user || isLocalAgent !== false) return;
    api
      .get<TunnelPublic>("/api/agent/tunnel/public")
      .then(setTunnel)
      .catch(() => setTunnel({ hostname: "", configured: false }));
  }, [user, isLocalAgent]);

  if (!user) return null;

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap flex-shrink-0 ${
      isActive ? "bg-accent text-slate-900" : "text-slate-300 hover:bg-panel2"
    }`;

  return (
    <nav className="bg-panel border-b border-slate-800 sticky top-0 z-20">
      <div className="flex items-center justify-between px-4 py-3 gap-3">
        <NavLink to="/dashboard" className="flex items-center gap-2 min-w-0 flex-shrink-0">
          <img src={logo} alt="" className="h-8 w-8 object-contain flex-shrink-0" />
          <span className="text-lg font-bold text-accent truncate">AI Sentinel</span>
        </NavLink>
        <button
          onClick={() => {
            logout();
            navigate("/login");
          }}
          className="px-3 py-2 rounded-lg text-sm font-medium text-slate-400 hover:bg-panel2 flex-shrink-0"
        >
          Salir
        </button>
      </div>
      {/* En mobile esta fila se desplaza horizontal en vez de amontonarse o
          desbordar la pantalla; en desktop entra entera sin necesidad de scroll. */}
      <div className="flex items-center gap-1 px-4 pb-3 overflow-x-auto">
        {/* Cámaras/Alertas/Agregar cámara sólo tienen sentido en el agente local
            (acceso directo a la red de casa) -- en el portal público (Railway)
            se ocultan para no mandar a nadie a un formulario que no puede
            funcionar ahí. isLocalAgent === null (todavía cargando) no oculta
            nada, para no hacer parpadear el menú. */}
        {isLocalAgent !== false && (
          <>
            <NavLink to="/dashboard" className={linkClass}>
              Cámaras
            </NavLink>
            <NavLink to="/alerts" className={linkClass}>
              Alertas
            </NavLink>
            <NavLink to="/onboarding" className={linkClass}>
              + Agregar cámara
            </NavLink>
          </>
        )}
        {/* Pestaña nueva, visible sólo en el portal central (ai-sentinel.puma-code.com):
            manda directo al dashboard REAL -- el mismo que ves cuando corrés el agente
            local -- pero servido por tu propia PC de casa a través del túnel. Es un link
            normal <a>, no un <NavLink> de react-router, porque apunta a otro dominio
            (cliente1.ai-sentinel.puma-code.com), no a una ruta interna de esta app. */}
        {isLocalAgent === false && tunnel?.configured && (
          <a
            href={`https://${tunnel.hostname}/dashboard`}
            className="px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap flex-shrink-0 text-slate-300 hover:bg-panel2"
          >
            Panel de control
          </a>
        )}
        <NavLink to="/billing" className={linkClass}>
          Suscripción
        </NavLink>
        <NavLink to="/download" className={linkClass}>
          Descargar
        </NavLink>
        {user.role === "admin" && (
          <NavLink to="/admin" className={linkClass}>
            Admin
          </NavLink>
        )}
      </div>
    </nav>
  );
}
