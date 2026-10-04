import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import logo from "../assets/logo-sentinel.png";

export default function Nav() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

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
        <NavLink to="/dashboard" className={linkClass}>
          Cámaras
        </NavLink>
        <NavLink to="/alerts" className={linkClass}>
          Alertas
        </NavLink>
        <NavLink to="/onboarding" className={linkClass}>
          + Agregar cámara
        </NavLink>
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
