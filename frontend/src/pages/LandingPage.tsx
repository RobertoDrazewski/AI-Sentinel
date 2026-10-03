import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import logo from "../assets/logo-sentinel.png";

/** Portada pública: una sola pantalla, sin scroll, fondo del circuito + logo
 * centrado con resplandor. Si ya hay sesión, va directo al panel en vez de
 * mostrar esta pantalla de nuevo. */
export default function LandingPage() {
  const { user, loading } = useAuth();

  if (!loading && user) return <Navigate to="/dashboard" replace />;

  return (
    <div
      className="relative h-dvh w-full overflow-y-auto flex flex-col items-center justify-center px-6 py-6 bg-bg bg-cover bg-center"
      style={{ backgroundImage: "url(/landing-bg.jpg)" }}
    >
      {/* Oscurece un poco el fondo para que el logo y el texto siempre se
          lean bien, sin importar qué tan clara salga esa zona de la foto. */}
      <div className="absolute inset-0 bg-bg/55" />

      <div className="relative flex flex-col items-center text-center gap-3 sm:gap-4 max-w-sm w-full my-auto">
        <img
          src={logo}
          alt="AI Sentinel"
          className="w-48 h-48 sm:w-72 sm:h-72 object-contain animate-sentinel-glow"
        />
        <div>
          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-amber-500 via-amber-300 to-sky-400 bg-clip-text text-transparent">
            AI Sentinel
          </h1>
          <p className="text-xs sm:text-sm tracking-[0.2em] text-slate-400 uppercase mt-1">by Puma Code</p>
        </div>
        <p className="text-sm sm:text-base text-slate-300">
          Convertí la cámara o el DVR que ya tenés en un sistema de seguridad inteligente que te avisa
          por Telegram al instante.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 w-full mt-2">
          <Link
            to="/register"
            className="flex-1 px-4 py-3 rounded-xl bg-accent text-slate-900 font-semibold text-center hover:brightness-95 transition"
          >
            Crear cuenta
          </Link>
          <Link
            to="/login"
            className="flex-1 px-4 py-3 rounded-xl bg-panel2/80 border border-slate-600 text-slate-100 font-semibold text-center hover:bg-panel2 transition"
          >
            Ingresar
          </Link>
        </div>
      </div>
    </div>
  );
}
